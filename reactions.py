import logging

import discord
from discord import client

from utils.grant_utils import (
    get_grant_proposal,
    add_grant_proposal,
    remove_grant_proposal,
    is_relevant_grant_proposal,
)
from utils.db_utils import DBUtil
from utils import db_utils
from utils.logging_config import log_handler, console_handler
from utils.validation import validate_roles
from utils.bot_utils import get_discord_client
from utils.const import REACTION_ON_BOT_MENTION, CANCEL_EMOJI_UNICODE, VOTING_CHANNEL_ID

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(log_handler)
logger.addHandler(console_handler)

db = DBUtil()
client = get_discord_client()


@client.event
async def on_message(message):
    """
    React with greetings emoji to any message where bot is mentioned.
    """
    if client.user in message.mentions:
        await message.add_reaction(REACTION_ON_BOT_MENTION)


@client.event
async def on_raw_reaction_add(payload):
    """
    Cancel a grant proposal if a L3 member reacts with a :x: emoji to the original message or the confirmation message.
    Parameters:
        payload (discord.RawReactionActionEvent): The event containing data about the reaction.
    """

    # Check if the reaction matches
    if payload.emoji.name != CANCEL_EMOJI_UNICODE:
        return

    # Check if the user role matches
    guild = client.get_guild(payload.guild_id)
    member = guild.get_member(payload.user_id)
    if not await validate_roles(member):
        return

    try:
        proposal = get_grant_proposal(reaction_message_id)
    except ValueError as e:
        logger.critical(f"Error while getting grant proposal: {e}")
        return

    # Check if the channel matches
    reaction_channel_id = guild.get_channel(payload.channel_id)
    reaction_message_id = payload.message_id
    if reaction_channel_id != VOTING_CHANNEL_ID:
        # TODO check if reaction was made to a wrong message - either to bot reply or original
        # proposer message, and send user private message in channel explaining where he should
        return

    # Check if the reaction message is a relevant lazy consensus voting
    if not is_relevant_grant_proposal(reaction_message_id):
        return

    #  Check whether the voter is the proposer himself
    if proposal.author_id == payload.user_id:
        # reply in original channel to the original proposal message with PROPOSAL_RESULT_PROPOSER_RESPONSE["CancelledByProposer"]
        # edit the message where reaction was made to PROPOSAL_RESULT_VOTING_CHANNEL_EDITED_MESSAGE with PROPOSAL_RESULT_VOTING_CHANNEL["CancelledByProposer"]
        # remove from DB
        return

    # Check if the threshold is reached
    # if it's not:
    # 1) add the person who voted to voters list and save it to DB
    # if it's reached:
    # 1) reply in original channel to the original proposal message with PROPOSAL_RESULT_PROPOSER_RESPONSE["CancelledByReachingThreshold"]
    # 2) edit the message where reaction was made to PROPOSAL_RESULT_VOTING_CHANNEL_EDITED_MESSAGE with PROPOSAL_RESULT_VOTING_CHANNEL["CancelledByReachingThreshold"]
    # 3) remove from DB

    # Remove the proposal from dictionary
    try:
        remove_grant_proposal(original_message_id)
    except ValueError as e:
        logger.critical(
            f"A cancel emoji was added to the response of the bot, but the original grant proposal message couldn't be found in the list of active proposals: {e}"
        )
        return
    logger.info("Cancelled grant proposal. message_id=%d", original_message_id)

    # Confirm that the grant proposal was cancelled in chat
    original_message = await reaction_channel_id.fetch_message(original_message_id)
    await original_message.reply(
        f"Proposal was cancelled by {member.mention} (friendly reminder: please make sure to explain why it was cancelled).",
    )
    logger.info(
        "Confirmed cancellation of grant proposal in chat. message_id=%d", original_message_id
    )
