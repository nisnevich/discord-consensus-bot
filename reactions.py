import logging

import discord
from discord import client

from main import grant_proposals
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
    if payload.message_id in grant_proposals:
        original_message_id = grant_proposals[payload.message_id]["message_id"]

    # Check if message is a pending grant proposal
    if original_message_id not in grant_proposals:
        return

    # Get member object and validate roles
    guild = client.get_guild(payload.guild_id)
    member = guild.get_member(payload.user_id)
    if not validate_roles(member):
        return

    # Cancel grant proposal
    del grant_proposals[original_message_id]
    conn.execute("DELETE FROM grant_proposals WHERE id = ?", (original_message_id,))
    conn.commit()
    logger.info("Cancelled grant proposal. message_id=%d", original_message_id)

    # Confirm that the grant proposal was cancelled in chat
    original_message = await guild.get_channel(payload.channel_id).fetch_message(
        original_message_id
    )
    await original_message.channel.send(
        f"Proposal was cancelled by {member.mention} (friendly reminder: please make sure you explain why it was cancelled).",
        reply_to_message_id=original_message.id,
    )
    logger.info(
        "Confirmed cancellation of grant proposal in chat. message_id=%d", original_message_id
    )

