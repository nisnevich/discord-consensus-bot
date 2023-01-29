import logging
import time

import discord

from utils.grant_utils import get_grant_proposal, add_grant_proposal, remove_grant_proposal
from utils.db_utils import DBUtil
from utils.const import *
from utils.logging_config import log_handler, console_handler
from utils.bot_utils import get_discord_client

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(log_handler)
logger.addHandler(console_handler)

db = DBUtil()
client = get_discord_client()


async def grant(voting_message_id):
    try:
        try:
            grant_proposal = get_grant_proposal(voting_message_id)
        except ValueError as e:
            logger.error("Grant proposal not found. voting_message_id=%d", voting_message_id)
            return

        mention = grant_proposal.mention
        amount = grant_proposal.amount
        description = grant_proposal.description
        channel_id = grant_proposal.channel_id
        result = ProposalResult.ACCEPTED

        # Retrieve the original proposal message
        original_channel = client.get_channel(grant_proposal.channel_id)
        original_message = await original_channel.fetch_message(grant_proposal.message_id)
        # Retrieve the voting message
        voting_channel = client.get_channel(VOTING_CHANNEL_ID)
        voting_message = await voting_channel.fetch_message(grant_proposal.voting_message_id)

        # Construct the grant message
        grant_message = GRANT_COMMAND_MESSAGE.format(
            prefix=DISCORD_COMMAND_PREFIX,
            grant_command=GRANT_PROPOSAL_COMMAND_NAME,
            mention=grant_proposal.mention,
            amount=grant_proposal.amount,
            description=grant_proposal.description,
            voting_url=voting_message.jump_url,
        )

        # Apply the grant
        try:
            channel = client.get_channel(GRANT_APPLY_CHANNEL_ID)
            await channel.send(grant_message)
            # Add "accepted" reactions to all messages
            if original_message:
                await original_message.add_reaction(REACTION_ON_PROPOSAL_ACCEPTED)
            if voting_message:
                await voting_message.add_reaction(REACTION_ON_PROPOSAL_ACCEPTED)
                await voting_message.add_reaction(EMOJI_HOORAY)
        except Exception as e:
            await voting_channel.send(
                f"Could not apply grant for {grant_proposal.mention}. cc {RESPONSIBLE_MENTION}",
            )
            logger.critical(
                "An error occurred while sending grant message, voting_message_id=%d",
                voting_message_id,
                exc_info=True,
            )
            # Throwing exception further because if the grant failed to apply, we don't want to do anything else
            raise e

        # Reply to the original proposal message, if it still exists, and if it wasn't send in the voting channel (to avoid unnecessary spam)
        if original_message and (voting_channel.id != original_channel.id):
            await original_message.reply(
                PROPOSAL_RESULT_PROPOSER_RESPONSE[result].format(
                    mention=grant_proposal.mention,
                    amount=grant_proposal.amount,
                )
            )
        else:
            logger.warning(
                "Warning: Looks like the proposer has removed the original proposal message. message_id=%d",
                grant_proposal.message_id,
            )

        # Update the proposal results in the voting channel
        if voting_message:
            await voting_message.edit(
                content=PROPOSAL_RESULT_VOTING_CHANNEL_EDITED_MESSAGE.format(
                    amount=grant_proposal.amount,
                    mention=grant_proposal.mention,
                    author=grant_proposal.author,
                    result=PROPOSAL_RESULT_VOTING_CHANNEL[result],
                    description=grant_proposal.description,
                    link_to_original_message=original_message.jump_url,
                )
            )
        else:
            await voting_channel.send(
                f"The {grant_proposal.amount} grant for {grant_proposal.mention} was applied, but I couldn't find the voting message in this channel. Was it removed? cc {RESPONSIBLE_MENTION}",
            )
            logger.warning(
                "Warning: The proposal message in the voting channel not found. voting_message_id=%d",
                voting_message_id,
            )

        # Remove grant proposal from dictionary
        try:
            await remove_grant_proposal(voting_message_id, db)
        except ValueError as e:
            logger.critical(f"Error while removing grant proposal: {e}")
            return
        logger.info("Successfully applied grant. voting_message_id=%d", voting_message_id)

    except Exception as e:
        try:
            # Try replying in Discord
            grant_proposal = get_grant_proposal(voting_message_id)
            channel = client.get_channel(grant_proposal.channel_id)
            original_message = await channel.fetch_message(voting_message_id)

            await original_message.reply(
                f"An unexpected error occurred when approving the grant. cc {RESPONSIBLE_MENTION}"
            )
        except Exception as e:
            logger.critical("Unable to reply in the chat that a critical error has occurred.")

        logger.critical(
            "Unexpected error in %s while approving the grant, voting_message_id=%s",
            __name__,
            voting_message_id,
            exc_info=True,
        )
