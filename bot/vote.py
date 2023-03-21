import discord
import asyncio
from datetime import datetime, timedelta

from bot.config.logging_config import log_handler, console_handler
from bot.config.const import *
from bot.config.schemas import Voters

from bot.utils.proposal_utils import (
    get_proposal,
    remove_proposal,
    is_relevant_proposal,
    add_voter,
    remove_voter,
    find_matching_voter,
    get_proposal_initiated_by,
    get_voters_with_vote,
)
from bot.utils.db_utils import DBUtil
from bot.utils.validation import validate_roles
from bot.utils.discord_utils import get_discord_client, get_message, send_dm
from bot.utils.formatting_utils import (
    get_amount_to_print,
    get_discord_countdown_plus_delta,
    get_mention_by_id,
    get_nickname_by_id_or_mention,
)

logger = logging.getLogger(__name__)
logger.setLevel(DEFAULT_LOG_LEVEL)
logger.addHandler(log_handler)
logger.addHandler(console_handler)

db = DBUtil()
client = get_discord_client()


async def is_valid_voting_reaction(payload):
    logger.debug("Verifying the reaction...")

    # Check if the reaction matches
    if payload.emoji.name != EMOJI_VOTING_NO and payload.emoji.name != EMOJI_VOTING_YES:
        return False
    logger.debug("Emoji is correct")

    # The bot adds voting reactions to each message as a template, so it should be filtered out
    if payload.user_id == BOT_ID:
        return False
    logger.debug("Voter is not the bot itself.")

    # Check if the user role matches
    guild = client.get_guild(payload.guild_id)
    member = guild.get_member(payload.user_id)
    if not await validate_roles(member):
        return False
    logger.debug("Role is correct")

    reaction_channel = guild.get_channel(payload.channel_id)

    # A hotfix for discord forums (the None channel is returned when a reaction is added to a message in a forum; though it works fine in other functions that use ctx.message.channel.id, such as propose)
    if not reaction_channel:
        logger.debug("Seems like a forum message.")
        return

    # When adding reaction, check if the user has attempted to vote on a wrong message - either the original proposer message, or the bots reply to it, associated with an active proposal though (in order to help onboard new users)
    if payload.event_type == "REACTION_ADD":
        incorrect_reaction_proposal = get_proposal_initiated_by(payload.message_id)
        if incorrect_reaction_proposal:
            # Remove reaction from the message (only in channels that are allowed for bot to manage messages/reactions), in order not to confuse other members
            if reaction_channel.id in CHANNELS_TO_REMOVE_HELPER_MESSAGES_AND_REACTIONS:
                reaction_message = await reaction_channel.fetch_message(payload.message_id)
                await reaction_message.remove_reaction(payload.emoji, member)

            # Retrieve the relevant voting message to send link to the user
            voting_message = await get_message(
                client, VOTING_CHANNEL_ID, incorrect_reaction_proposal.voting_message_id
            )
            # Send private message to user
            dm_channel = await member.create_dm()
            await dm_channel.send(
                HELP_MESSAGE_VOTED_INCORRECTLY.format(voting_link=voting_message.jump_url)
            )

    # Check if this is a voting channel
    if reaction_channel.id != VOTING_CHANNEL_ID:
        return False
    logger.debug("Channel is correct")

    # Check if the reaction message is a relevant lazy consensus voting
    if not is_relevant_proposal(payload.message_id):
        return False
    logger.debug("Proposal is correct")
    return True


@client.event
async def on_raw_reaction_remove(payload):
    logger.debug("Removing a reaction: %s", payload.event_type)
    try:
        # Check if the reaction was made by valid user to a valid voting message
        if not await is_valid_voting_reaction(payload):
            return

        # Get the proposal (it was already validated that it exists)
        proposal = get_proposal(payload.message_id)

        # Error handling - retrieve the voter object from the DB
        voter = find_matching_voter(payload.user_id, payload.message_id)
        if not voter:
            logger.warning(
                "Warning: Unable to find in the DB a user whose voting reaction was presented on active proposal. channel=%s, message=%s, user=%s, proposal=%s",
                payload.channel_id,
                payload.message_id,
                payload.user_id,
                proposal,
            )
            return

        # Remove the voter from the list of voters for the grant proposal
        await remove_voter(proposal, voter)

    except Exception as e:
        try:
            # Try replying in Discord
            message = await get_message(client, payload.channel_id, payload.message_id)
            await message.reply(
                f"An unexpected error occurred when handling reaction removal. cc {RESPONSIBLE_MENTION}"
            )
        except Exception as e:
            logger.critical("Unable to reply in the chat that a critical error has occurred.")

        logger.critical(
            "Unexpected error in %s while removing vote (reaction), channel=%s, message=%s, user=%s",
            __name__,
            payload.channel_id,
            payload.message_id,
            payload.user_id,
            exc_info=True,
        )


async def cancel_proposal(proposal, reason, voting_message):
    # Extracting dynamic data to fill messages
    # Don't remove unused variables because messages texts change too often
    mention_author = get_mention_by_id(proposal.author_id)
    description_of_proposal = proposal.description

    # Create lists of voters
    list_of_voters_for = []
    list_of_voters_against = []
    for voter in proposal.voters:
        voter_mention = get_mention_by_id(voter.user_id)
        if int(voter.value) == Vote.YES.value:
            list_of_voters_for.append(voter_mention)
        else:
            list_of_voters_against.append(voter_mention)
    number_of_voters_for = len(list_of_voters_for)
    list_of_voters_for = VOTERS_LIST_SEPARATOR.join(list_of_voters_for)
    list_of_voters_against = VOTERS_LIST_SEPARATOR.join(list_of_voters_against)

    # Retrieve links to the messages
    original_message = await get_message(client, proposal.channel_id, proposal.message_id)
    link_to_voting_message = voting_message.jump_url
    link_to_initial_proposer_message = original_message.jump_url if original_message else None
    if not proposal.not_financial:
        mention_recipient = proposal.recipient_ids
        amount_of_allocation = get_amount_to_print(proposal.amount)

    # Filling the proposer response message based on the reason of cancelling
    if reason == ProposalResult.CANCELLED_BY_PROPOSER:
        if proposal.not_financial:
            response_to_proposer = GRANTLESS_PROPOSAL_RESULT_PROPOSER_RESPONSE[reason].format(
                author=mention_author
            )
        else:
            response_to_proposer = GRANT_PROPOSAL_RESULT_PROPOSER_RESPONSE[reason].format(
                author=mention_author
            )
        log_message = "(by the proposer)"
    elif reason == ProposalResult.CANCELLED_BY_REACHING_NEGATIVE_THRESHOLD:
        if proposal.not_financial:
            response_to_proposer = GRANTLESS_PROPOSAL_RESULT_PROPOSER_RESPONSE[reason].format(
                author=mention_author,
                threshold=LAZY_CONSENSUS_THRESHOLD_NEGATIVE,
                voting_link=link_to_voting_message,
            )
        else:
            response_to_proposer = GRANT_PROPOSAL_RESULT_PROPOSER_RESPONSE[reason].format(
                author=mention_author,
                threshold=LAZY_CONSENSUS_THRESHOLD_NEGATIVE,
                voting_link=link_to_voting_message,
            )
        log_message = "(by reaching negative threshold_negative)"
    elif reason == ProposalResult.CANCELLED_BY_NOT_REACHING_POSITIVE_THRESHOLD:
        if proposal.not_financial:
            response_to_proposer = GRANTLESS_PROPOSAL_RESULT_PROPOSER_RESPONSE[reason].format()
        else:
            response_to_proposer = GRANT_PROPOSAL_RESULT_PROPOSER_RESPONSE[reason].format()
        log_message = "(by not reaching positive threshold)"

    # Filling the voting channel message based on the reason of cancelling
    if reason == ProposalResult.CANCELLED_BY_PROPOSER:
        edit_in_voting_channel = PROPOSAL_CANCELLED_VOTING_CHANNEL[reason].format(
            author=mention_author, link_to_original_message=link_to_initial_proposer_message
        )
    elif reason == ProposalResult.CANCELLED_BY_REACHING_NEGATIVE_THRESHOLD:
        edit_in_voting_channel = PROPOSAL_CANCELLED_VOTING_CHANNEL[reason].format(
            threshold=LAZY_CONSENSUS_THRESHOLD_NEGATIVE,
            voters_list=list_of_voters_against,
            link_to_original_message=link_to_initial_proposer_message,
        )
    elif reason == ProposalResult.CANCELLED_BY_NOT_REACHING_POSITIVE_THRESHOLD:
        edit_in_voting_channel = PROPOSAL_CANCELLED_VOTING_CHANNEL[reason].format(
            supporters_number=number_of_voters_for,
            yes_voting_reaction=EMOJI_VOTING_YES,
            supporters_list=f" ({list_of_voters_for})" if list_of_voters_for else "",
            threshold=proposal.threshold_positive,
            link_to_original_message=link_to_initial_proposer_message,
        )

    if original_message:
        await original_message.add_reaction(REACTION_ON_PROPOSAL_CANCELLED)
    # Reply in the original channel, unless it's not the voting channel itself (then not replying to avoid flooding)
    if original_message and voting_message.channel.id != original_message.channel.id:
        message = await original_message.reply(response_to_proposer)
        # Remove embeds
        await message.edit(suppress=True)
    # Edit the proposal in the voting channel; suppress=True will remove embeds
    await voting_message.edit(content=edit_in_voting_channel, suppress=True)

    # Add history item for analytics
    await db.add_proposals_history_item(proposal, reason)
    logger.debug(
        "Added history item, voting_message_id=%d, result=%s",
        proposal.voting_message_id,
        reason,
    )
    # Remove the proposal
    await remove_proposal(proposal.voting_message_id, db)
    logger.info(
        "Cancelled %s %s. voting_message_id=%d",
        "grantless proposal" if proposal.not_financial else "proposal with a grant",
        log_message,
        proposal.voting_message_id,
    )


@client.event
async def on_raw_reaction_add(payload):
    """
    Cancel a grant proposal if a L3 member reacts with a :x: emoji to the original message or the confirmation message.
    Parameters:
        payload (discord.RawReactionActionEvent): The event containing data about the reaction.
    """

    async def remove_reaction_and_send_dm(client, payload, message):
        """
        Creates DM channel, replies to user with the given message, and removes the reaction added
        in a given payload object.
        """
        # Create DM channel (not using send_dm function here, because the 'member' is used to remove the reaction later)
        guild = client.get_guild(payload.guild_id)
        member = guild.get_member(payload.user_id)
        dm_channel = await member.create_dm()
        # Reply the user in DM
        await dm_channel.send(message)
        # Remove the reaction
        reaction_message = await get_message(client, payload.channel_id, payload.message_id)
        await reaction_message.remove_reaction(payload.emoji, member)

    try:
        logger.debug("Adding a reaction: %s", payload.event_type)

        # Check if it's a valid voting reaction
        if not await is_valid_voting_reaction(payload):
            # If not, check if the reaction is a heart emoji, to double it (just for fun)
            if payload.emoji.name in HEART_EMOJI_LIST:
                message = await get_message(client, payload.channel_id, payload.message_id)
                await message.add_reaction(payload.emoji)
            return

        # Don't allow to vote if recovery is in progress
        if db.is_recovery():
            # Remove the vote emoji, reply to user and exit
            await remove_reaction_and_send_dm(client, payload, VOTING_PAUSED_RECOVERY_RESPONSE)
            logger.info(
                "Rejecting the vote from %s because recovery is in progress.",
                member.mention,
            )
            return

        # Retrieve the proposal
        proposal = get_proposal(payload.message_id)
        # Retrieve the voting message (to format the replies of the bot later)
        voting_message = await get_message(client, payload.channel_id, payload.message_id)

        # Check if the user has already voted for this proposal
        voter = find_matching_voter(payload.user_id, payload.message_id)
        logger.debug("Voter: %s", voter)
        if voter:
            # Remove the vote emoji, reply to user and exit
            await remove_reaction_and_send_dm(
                client,
                payload,
                ERROR_MESSAGE_ALREADY_VOTED.format(link_to_voting_message=voting_message.jump_url),
            )
            logger.info(
                "The user has already voted on this proposal: channel=%s, message=%s, user=%s, proposal=%s, voter=%s",
                payload.channel_id,
                payload.message_id,
                payload.user_id,
                proposal,
                voter,
            )
            return
        logger.debug("User hasn't voted on this proposal before")

        # If it's a positive vote and the author is the proposer himself, don't count the vote,
        if payload.emoji.name == EMOJI_VOTING_YES and int(proposal.author_id) == payload.user_id:
            # Remove the vote emoji, reply to user and exit
            await remove_reaction_and_send_dm(
                client, payload, ERROR_MESSAGE_AUTHOR_SUPPORTING_OWN_PROPOSAL
            )
            logger.info(
                "The author can't upvote their own proposal: proposal=%s, voter=%s",
                proposal,
                voter,
            )
            return

        # Add voter to DB and dict
        await add_voter(
            proposal,
            Voters(
                user_id=payload.user_id,
                user_nickname=get_nickname_by_id_or_mention(payload.user_id),
                voting_message_id=proposal.voting_message_id,
                value=Vote.YES.value if payload.emoji.name == EMOJI_VOTING_YES else Vote.NO.value,
            ),
        )
        logger.info(
            "Added vote=%s of user_id=%s, total %d voters in voting_message_id=%d",
            Vote.YES.value if payload.emoji.name == EMOJI_VOTING_YES else Vote.NO.value,
            payload.user_id,
            len(proposal.voters),
            proposal.voting_message_id,
        )
        # If the vote is positive, stop here after adding to DB
        if payload.emoji.name == EMOJI_VOTING_YES:
            return

        # If the vote is negative, continue
        # Check whether the voter is the proposer himself, and then cancel the proposal
        if int(proposal.author_id) == payload.member.id:
            logger.debug("The proposer voted against, cancelling")
            await cancel_proposal(proposal, ProposalResult.CANCELLED_BY_PROPOSER, voting_message)
            return
        logger.debug("The proposer isn't the author of the proposal")

        # Check if the threshold_negative is reached
        if len(get_voters_with_vote(proposal, Vote.NO)) >= proposal.threshold_negative:
            logger.debug("Threshold is reached, cancelling")
            await cancel_proposal(
                proposal, ProposalResult.CANCELLED_BY_REACHING_NEGATIVE_THRESHOLD, voting_message
            )
        # If not, DM user notifying that his vote was counted
        else:
            await send_dm(
                payload.guild_id,
                payload.user_id,
                HELP_MESSAGE_VOTED_AGAINST.format(
                    author=get_mention_by_id(proposal.author_id),
                    countdown=get_discord_countdown_plus_delta(
                        proposal.closed_at - datetime.utcnow()
                    ),
                    cancel_emoji=EMOJI_VOTING_NO,
                    voting_link=voting_message.jump_url,
                ),
            )
    except Exception as e:
        try:
            # Try replying in Discord
            message = await get_message(client, payload.channel_id, payload.message_id)

            await message.reply(
                f"An unexpected error occurred when handling reaction adding. cc {RESPONSIBLE_MENTION}"
            )
        except Exception as e:
            logger.critical("Unable to reply in the chat that a critical error has occurred.")

        logger.critical(
            "Unexpected error in %s while voting (adding reaction), channel=%s, message=%s, user=%s",
            __name__,
            payload.channel_id,
            payload.message_id,
            payload.user_id,
            exc_info=True,
        )
