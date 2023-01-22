import asyncio
import logging


from discord.ext import commands
from grant import grant

from grant import grant

from utils.const import *
import utils.db_utils
from utils.grant_utils import get_grant_proposal, add_grant_proposal, remove_grant_proposal
from utils.db_utils import DBUtil
from utils.logging_config import log_handler, console_handler
from utils.validation import validate_roles, validate_grant_message
from utils.bot_utils import get_discord_client
from utils.formatting_utils import get_discord_timestamp_plus_delta

from schemas.grant_proposals import GrantProposals

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(log_handler)
logger.addHandler(console_handler)

db = DBUtil()
client = get_discord_client()


async def approve_grant_proposal(message_id):
    """
    Loop until the timer reaches GRANT_PROPOSAL_TIMER_SECONDS days. Every minute, the timer is incremented by 60 seconds and updated in the database. If the timer ends, the grant proposal is approved and the entry is removed from the dictionary and database.
    """
    try:
        grant_proposal = get_grant_proposal(message_id)
    except ValueError as e:
        logger.error(f"Error while getting grant proposal: {e}")
        return
    await db.add(grant_proposal)
    while grant_proposal.timer < GRANT_PROPOSAL_TIMER_SECONDS:
        await asyncio.sleep(GRANT_PROPOSAL_TIMER_SLEEP_SECONDS)
        grant_proposal.timer += GRANT_PROPOSAL_TIMER_SLEEP_SECONDS
        await db.commit()
    try:
        await grant(message_id)
    except ValueError as e:
        logger.error(f"Error while removing grant proposal: {e}")


@client.command(name=GRANT_PROPOSAL_COMMAND_NAME)
async def grant_proposal(ctx, mention=None, amount=None, *description):
    """
    Submit a grant proposal to the Discord channel. The proposal will be approved after GRANT_PROPOSAL_TIMER_SECONDS unless a L3 member reacts with a :x: emoji to the original message or the confirmation message.
    Parameters:
        ctx (commands.Context): The context in which the command was called.
        mention (str): The mention of the user the grant is being proposed to.
        amount (str): The amount of the grant being proposed.
        description (str): The description of the grant being proposed.
    """
    description = ' '.join(description)

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
            return
        # If validation succeeded, cast 'amount' from string to integer
        amount = int(amount)

        # Add grant proposal to dictionary and database
        new_grant_proposal = GrantProposals(
            message_id=ctx.message.id,
            channel_id=ctx.message.channel.id,
            mention=mention,
            amount=amount,
            description=description,
            timer=0,
        )
        add_grant_proposal(new_grant_proposal)
        await db.add(new_grant_proposal)

        logger.info(
            "Inserted data: message_id=%d, channel_id=%d, mention=%s, amount=%d, description=%s, timer=%d",
            ctx.message.id,
            ctx.message.channel.id,
            mention,
            amount,
            description,
            0,
        )

        client.loop.create_task(approve_grant_proposal(ctx.message.id))
        logger.info("Added task to event loop to approve message_id=%d", ctx.message.id)

        # Send confirmation message
        await original_message.reply(
            PROPOSAL_ACCEPTED_RESPONSE.format(
                author=ctx.message.author.mention,
                time_hours=int(
                    GRANT_PROPOSAL_TIMER_SECONDS / 60 / 60,
                ),
                date_finish=get_discord_timestamp_plus_delta(GRANT_PROPOSAL_TIMER_SECONDS),
                mention=mention,
            )
        )
        logger.info(
            "Sent confirmation message for grant proposal with message_id=%d", ctx.message.id
        )

    except Exception as e:
        await ctx.send(
            "An unexpected error occurred, proposal wasn't added. cc " + RESPONSIBLE_MENTION
        )
        logger.critical("Unexpected error in %s", __name__, exc_info=True)
        traceback.print_exc()
