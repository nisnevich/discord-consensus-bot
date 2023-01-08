import asyncio
import logging

from discord import client
from discord.ext import commands

from utils.const import *
import utils.db_utils
from main import grant_proposals
from utils import db_utils
from utils.logging_config import log_handler
from utils.validation import validate_roles, validate_grant_message

logger = logging.getLogger(__name__)
logger.addHandler(log_handler)

conn = db_utils.connect_db()

@client.command()
async def approve_grant_proposal(message_id, channel_id, mention, amount, description):
    """
    Loop until the timer reaches GRANT_PROPOSAL_TIMER_SECONDS days. Every minute, the timer is incremented by 60 seconds and updated in the database. If the timer ends, the grant proposal is approved and the entry is removed from the dictionary and database.
    """
    grant_proposal = grant_proposals[message_id]
    while grant_proposal["timer"] < utils.GRANT_PROPOSAL_TIMER_SECONDS:
        await asyncio.sleep(utils.GRANT_PROPOSAL_TIMER_SLEEP_SECONDS)
        grant_proposal["timer"] += utils.GRANT_PROPOSAL_TIMER_SLEEP_SECONDS
        conn.execute(
            "UPDATE grant_proposals SET timer = ? WHERE id = ?",
            (grant_proposal["timer"], message_id),
        )
        conn.commit()
    if message_id in grant_proposals:
        # Approve grant proposal
        await client.get_command("grant")(channel_id, message_id, mention, amount, description=description)
        del grant_proposals[message_id]



@client.command()
async def grant_proposal(client, ctx, mention, amount, *, description=""):
    """
    Submit a grant proposal to the Discord channel. The proposal will be approved after GRANT_PROPOSAL_TIMER_SECONDS unless a L3 member reacts with a :x: emoji to the original message or the confirmation message.
    Parameters:
        ctx (commands.Context): The context in which the command was called.
        mention (str): The mention of the user the grant is being proposed to.
        amount (str): The amount of the grant being proposed.
        description (str, optional): The description of the grant being proposed.
    """
    try:
        original_message = await ctx.fetch_message(ctx.message.id)

        # Validity checks
        if not validate_roles(ctx.message.author):
            await original_message.channel.send("Error: You do not have the required role to use this command.")
            logger.warning("Unauthorized user. message_id=%d", original_message.id)
            return
        if not validate_grant_message(ctx, original_message, amount):
            return

        # Add grant proposal to dictionary and database
        grant_proposals[ctx.message.id] = {
            "mention": mention,
            "amount": amount,
            "description": description,
            "timer": 0,  # Add timer field to store elapsed time
            "message_id": ctx.message.id,
            "channel_id": ctx.message.channel.id,
        }
        conn.execute(
            "INSERT INTO grant_proposals (mention, amount, description, timer, message_id, channel_id) VALUES (?, ?, ?, ?, ?, ?)",
            (mention, amount, description, 0, ctx.message.id, ctx.message.channel.id),
        )
        conn.commit()
        logger.info(
            "Inserted data: mention=%s, amount=%d, description=%s, timer=%d, message_id=%d, channel_id=%d",
            mention,
            amount,
            description,
            0,
            ctx.message.id,
            ctx.message.channel.id,
        )

        client.loop.create_task(approve_grant_proposal(ctx.message.id, ctx.message.channel.id, mention, amount, description))

        # Send confirmation message
        await original_message.channel.send(
            f"{ctx.message.author.mention}, your grant proposal has been accepted. If any L3 member disagrees, they can react with the :x: emoji to this message or the original message.",
            reply=original_message,
        )
        logger.info(
            "Sent confirmation message for grant proposal with message_id=%d", ctx.message.id
        )

    except Exception as e:
        await ctx.send("Error: An unexpected error occurred, proposal wasn't added. cc " + RESPONSIBLE_MENTION, reply=ctx.message)
        logger.critical("An error occurred", exc_info=True)

