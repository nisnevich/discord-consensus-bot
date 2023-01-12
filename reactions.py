import logging

import discord
from discord import client

from utils.grant_utils import get_grant_proposal, add_grant_proposal, remove_grant_proposal
from utils import db_utils
from utils.logging_config import log_handler
from utils.validation import validate_roles

logger = logging.getLogger(__name__)
logger.addHandler(log_handler)

conn = db_utils.connect_db()


@client.event
async def on_raw_reaction_add(client, payload):
    """
    Cancel a grant proposal if a L3 member reacts with a :x: emoji to the original message or the confirmation message.
    Parameters:
        payload (discord.RawReactionActionEvent): The event containing data about the reaction.
    """

    # Check if reaction is a :x: emoji
    if payload.emoji.name != "x":
        return
    # Check if the reaction was made to the original grant proposal message or the confirmation message
    # If the reaction was made to the confirmation message, we need to get the original grant proposal message
    original_message_id = payload.message_id
    try:
        proposal = get_grant_proposal(payload.message_id)
        original_message_id = proposal["message_id"]
    except ValueError as e:
        logger.critical(f"Error while getting grant proposal: {e}")
        return

    # Get member object and validate roles
    guild = client.get_guild(payload.guild_id)
    member = guild.get_member(payload.user_id)
    if not validate_roles(member):
        return

    try:
        remove_grant_proposal(original_message_id)
    except ValueError as e:
        logger.critical(
            f"A cancel emoji was added to the response of the bot, but the original grant proposal message couldn't be found in the list of active proposals: {e}"
        )
        return

    conn.execute("DELETE FROM grant_proposals WHERE id = ?", (original_message_id,))
    conn.commit()
    logger.info("Cancelled grant proposal. message_id=%d", original_message_id)

    # Confirm that the grant proposal was cancelled in chat
    original_message = await guild.get_channel(payload.channel_id).fetch_message(
        original_message_id
    )
    await original_message.channel.send(
        f"Proposal was cancelled by {member.mention} (friendly reminder: please make sure to explain why it was cancelled).",
        reply_to_message_id=original_message.id,
    )
    logger.info(
        "Confirmed cancellation of grant proposal in chat. message_id=%d", original_message_id
    )
