import asyncio
import logging

from discord.ext import commands
from grant import grant

from utils.const import *
import utils.db_utils
from utils.grant_utils import get_grant_proposal, add_grant_proposal, remove_grant_proposal
from utils.db_utils import DBUtil
from utils.logging_config import log_handler
from utils.validation import validate_roles, validate_grant_message
from utils.bot_utils import get_discord_client

from schemas.grant_proposals import GrantProposals

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(log_handler)

session = DBUtil().session
client = get_discord_client()


async def approve_grant_proposal(message_id, channel_id, mention, amount, description):
    """
    Loop until the timer reaches GRANT_PROPOSAL_TIMER_SECONDS days. Every minute, the timer is incremented by 60 seconds and updated in the database. If the timer ends, the grant proposal is approved and the entry is removed from the dictionary and database.
    """
    try:
        grant_proposal = get_grant_proposal(message_id)
    except ValueError as e:
        logger.error(f"Error while getting grant proposal: {e}")
        return
    while grant_proposal.timer < utils.GRANT_PROPOSAL_TIMER_SECONDS:
        await asyncio.sleep(utils.GRANT_PROPOSAL_TIMER_SLEEP_SECONDS)
        grant_proposal.timer += utils.GRANT_PROPOSAL_TIMER_SLEEP_SECONDS
        session.commit()
        # conn.execute(
        #     "UPDATE grant_proposals SET timer = ? WHERE id = ?",
        #     (grant_proposal["timer"], message_id),
        # )
        # conn.commit()
    try:
        await grant(channel_id, message_id, mention, amount, description=description)
        remove_grant_proposal(message_id)
    except ValueError as e:
        logger.error(f"Error while removing grant proposal: {e}")


@client.command(name=GRANT_PROPOSAL_COMMAND_NAME)
async def grant_proposal(ctx, mention=None, amount=None, description=None):
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
        if not await validate_roles(ctx.message.author):
            await original_message.reply("Error: you must have Layer 3 role to use this command.")
            logger.warning("Unauthorized user. message_id=%d", original_message.id)
            return
        if not mention or not amount or not description:
            await original_message.reply(
                COMMAND_FORMAT_RESPONSE.format(author=ctx.message.author.mention)
            )
            return
        if not await validate_grant_message(original_message, amount, description):
            # FIXME: add SQL injection validation
            return

        # Add grant proposal to dictionary and database
        new_grant_proposal = GrantProposals(
            id=ctx.message.id,
            mention=mention,
            amount=amount,
            description=description,
            timer=0,
            channel_id=ctx.message.channel.id
        )
        add_grant_proposal(new_grant_proposal)
        session.add(new_grant_proposal)
        session.commit()

        # conn.execute(
        #     "INSERT INTO grant_proposals (message_id, mention, amount, description, timer, channel_id) VALUES (?, ?, ?, ?, ?, ?)",
        #     (ctx.message.id, mention, amount, description, 0, ctx.message.channel.id),
        # )
        # conn.commit()

        logger.info(
            "Inserted data: message_id=%d, mention=%s, amount=%d, description=%s, timer=%d, channel_id=%d",
            ctx.message.id,
            mention,
            amount,
            description,
            0,
            ctx.message.channel.id,
        )
        # TODO backup DB somewhere remote after inserting or deleting any grant proposal, so if it gets lots then no proposals would be lost (if the timer will reset it's not a big deal compared to wasting proposals themselves)

        client.loop.create_task(
            approve_grant_proposal(
                ctx.message.id, ctx.message.channel.id, mention, amount, description
            )
        )

        # Send confirmation message
        await original_message.channel.send(
            f"{ctx.message.author.mention}, your grant proposal has been accepted. If any L3 member disagrees, they can react with the :x: emoji to this message or the original message.",
            reply=original_message,
        )
        logger.info(
            "Sent confirmation message for grant proposal with message_id=%d", ctx.message.id
        )

    except Exception as e:
        await ctx.send(
            "Error: An unexpected error occurred, proposal wasn't added. cc " + RESPONSIBLE_MENTION,
            reply=ctx.message,
        )
        logger.critical("An error occurred", exc_info=True)
