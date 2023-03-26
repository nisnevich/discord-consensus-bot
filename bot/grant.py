from bot.utils.proposal_utils import (
    get_proposal,
    remove_proposal,
    proposal_lock,
    save_proposal_to_history,
)
from bot.utils.db_utils import DBUtil
from bot.config.const import *
from bot.config.logging_config import log_handler, console_handler
from bot.utils.discord_utils import get_discord_client, get_message
from bot.utils.formatting_utils import get_amount_to_print, get_mention_by_id


logger = logging.getLogger(__name__)
logger.setLevel(DEFAULT_LOG_LEVEL)
logger.addHandler(log_handler)
logger.addHandler(console_handler)

db = DBUtil()
client = get_discord_client()


async def grant(voting_message_id):
    try:
        # Acquire the proposal lock when accepting or cancelling to avoid concurrency errors
        async with proposal_lock:
            try:
                proposal = get_proposal(voting_message_id)
            except ValueError as e:
                logger.error("Proposal not found. voting_message_id=%d", voting_message_id)
                return

            result = ProposalResult.ACCEPTED

            # Retrieve the original proposal message
            # get_message is not used here for a reason - the channel variables are reused later
            original_channel = client.get_channel(proposal.channel_id)
            original_message = await original_channel.fetch_message(proposal.message_id)
            link_to_original_message = original_message.jump_url if original_message else None
            # Retrieve the voting message
            voting_channel = client.get_channel(VOTING_CHANNEL_ID)
            voting_message = await voting_channel.fetch_message(proposal.voting_message_id)

            # Applying the grant if the proposal isn't grantless
            if not proposal.not_financial:
                for recipient in proposal.finance_recipients:
                    # Extract array of recipient ids
                    ids = recipient.recipient_ids.split(DB_ARRAY_COLUMN_SEPARATOR)
                    # Construct the grant message
                    grant_message = GRANT_COMMAND_LAZY_CONSENSUS_MESSAGE.format(
                        prefix=DISCORD_COMMAND_PREFIX,
                        grant_command=GRANT_APPLY_COMMAND_NAME,
                        # Convert recipient ids to mentions, and write them separated by space
                        mention=" ".join(get_mention_by_id(id) for id in ids),
                        amount=get_amount_to_print(recipient.amount),
                        author=get_mention_by_id(proposal.author_id),
                        voting_url=voting_message.jump_url,
                    )
                    # Apply the grant
                    channel = client.get_channel(GRANT_APPLY_CHANNEL_ID)
                    message = await channel.send(grant_message)
                    # Remove embeds
                    await message.edit(suppress=True)

            # Add "accepted" reactions to all messages
            if original_message:
                await original_message.add_reaction(REACTION_ON_PROPOSAL_ACCEPTED)
            if voting_message:
                await voting_message.add_reaction(REACTION_ON_PROPOSAL_ACCEPTED)
                await voting_message.add_reaction(EMOJI_HOORAY)

            # Reply to the original proposal message, if it still exists, and if it wasn't send in the voting channel (to avoid flooding)
            if original_message and (voting_channel.id != original_channel.id):
                if not proposal.not_financial:
                    await original_message.reply(
                        GRANT_PROPOSAL_RESULT_PROPOSER_RESPONSE[result].format(
                            amount=get_amount_to_print(proposal.total_amount),
                        )
                    )
                else:
                    await original_message.reply(
                        GRANTLESS_PROPOSAL_RESULT_PROPOSER_RESPONSE[result].format()
                    )
            elif not original_message:
                logger.warning(
                    "Warning: Looks like the proposer has removed the original proposal message. message_id=%d",
                    proposal.message_id,
                )

            # Compose the list of supporters
            supported_by = PROPOSAL_ACCEPTED_SUPPORTED_BY_VOTING_CHANNEL_EDIT.format(
                supporters_list=COMMA_LIST_SEPARATOR.join(
                    get_mention_by_id(voter.user_id)
                    for voter in proposal.voters
                    if int(voter.value) == Vote.YES.value
                )
            )
            # Update the proposal results in the voting channel
            if voting_message:
                if proposal.not_financial:
                    await voting_message.edit(
                        content=GRANTLESS_PROPOSAL_ACCEPTED_VOTING_CHANNEL_EDIT.format(
                            author=get_mention_by_id(proposal.author_id),
                            description=proposal.description,
                            supported_by=supported_by if FULL_CONSENSUS_ENABLED else "",
                            # TODO#9 if original_message is None, message should be different
                            link_to_original_message=link_to_original_message,
                        ),
                        suppress=True,
                    )
                else:
                    await voting_message.edit(
                        content=GRANT_PROPOSAL_ACCEPTED_VOTING_CHANNEL_EDIT.format(
                            amount_sum=get_amount_to_print(proposal.total_amount),
                            description=proposal.description,
                            supported_by=supported_by if FULL_CONSENSUS_ENABLED else "",
                            author=get_mention_by_id(proposal.author_id),
                            # TODO#9 if original_message is None, message should be different
                            link_to_original_message=link_to_original_message,
                        ),
                        suppress=True,
                    )
            else:
                # Handling the case when voting message was somehow removed from the channel
                if not proposal.not_financial:
                    message = await voting_channel.send(
                        ERROR_MESSAGE_PROPOSAL_WITH_GRANT_VOTING_LINK_REMOVED.format(
                            amount=get_amount_to_print(proposal.total_amount),
                            link_to_original_message=f"Original message: {link_to_original_message}",
                            RESPONSIBLE_MENTION=RESPONSIBLE_MENTION,
                        )
                    )
                    # Remove embeds
                    await message.edit(suppress=True)
                else:
                    message = await voting_channel.send(
                        ERROR_MESSAGE_GRANTLESS_PROPOSAL_VOTING_LINK_REMOVED.format(
                            author=get_mention_by_id(proposal.author_id),
                            link_to_original_message=f"Original message: {link_to_original_message}",
                            RESPONSIBLE_MENTION=RESPONSIBLE_MENTION,
                        )
                    )
                    # Remove embeds
                    await message.edit(suppress=True)
                logger.warning(
                    "Warning: The proposal message in the voting channel not found. voting_message_id=%d",
                    voting_message_id,
                )

            # Add history item for analytics
            await save_proposal_to_history(db, proposal, result)
            logger.info("Successfully approved proposal. voting_message_id=%d", voting_message_id)

    except Exception as e:
        try:
            # Try replying in Discord
            proposal = get_proposal(voting_message_id)
            channel = client.get_channel(proposal.channel_id)
            original_message = await channel.fetch_message(voting_message_id)

            await original_message.reply(
                f"An unexpected error occurred when approving the proposal. cc {RESPONSIBLE_MENTION}"
            )
        except Exception as e:
            logger.critical("Unable to reply in the chat that a critical error has occurred.")

        logger.critical(
            "Unexpected error in %s while approving the proposal, voting_message_id=%s",
            __name__,
            voting_message_id,
            exc_info=True,
        )
