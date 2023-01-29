import asyncio
import logging


from discord.ext import commands
from grant import grant

from grant import grant

from utils.const import *
import utils.db_utils
from utils.grant_utils import (
    get_grant_proposal,
    add_grant_proposal,
    remove_grant_proposal,
    is_relevant_grant_proposal,
)
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
    logger.info("Running approval coroutine for message_id=%d", message.id)
    try:
        grant_proposal = get_grant_proposal(message_id)
    except ValueError as e:
        logger.error(f"Error while getting grant proposal: {e}")
        return
    while grant_proposal.timer < GRANT_PROPOSAL_TIMER_SECONDS:
        # If proposal was cancelled, it will be removed from dictionary (see on_raw_reaction_add)
        if not is_relevant_grant_proposal(message_id):
            return
        await asyncio.sleep(GRANT_PROPOSAL_TIMER_SLEEP_SECONDS)
        grant_proposal.timer += GRANT_PROPOSAL_TIMER_SLEEP_SECONDS
        await db.commit()
    try:
        # Double check to make sure proposal wasn't cancelled
        if not is_relevant_grant_proposal(message_id):
            return
        await grant(message_id)
    except ValueError as e:
        logger.error(f"Error while removing grant proposal: {e}")


@client.command(name=GRANT_PROPOSAL_COMMAND_NAME)
async def grant_proposal(ctx, mention=None, amount=None, *description):
    f"""
    Submit a grant proposal. The proposal will be approved after
    {GRANT_PROPOSAL_TIMER_SECONDS} unless a Layer 3 member reacts with a :x: emoji to the original message or the confirmation message.
    Parameters:
        ctx (commands.Context): The context in which the command was called.
        mention: The mention of the user the grant is being proposed to.
        amount: The amount of the grant being proposed.
        description: The description of the grant being proposed.
    """
    description = ' '.join(description)
    print("I see command!")

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

        # Add proposal to the voting channel
        channel = client.get_channel(VOTING_CHANNEL_ID)
        voting_message = await channel.send(NEW_PROPOSAL_VOTING_CHANNEL_MESSAGE)

        # Reply to the proposer
        bot_response_message = await original_message.reply(
            NEW_PROPOSAL_SAME_CHANNEL_RESPONSE.format(
                author=ctx.message.author.mention,
                mention=mention,
                amount=amount,
                #  time_hours=int(
                #      GRANT_PROPOSAL_TIMER_SECONDS / 60 / 60,
                #  ),
                #  date_finish=get_discord_timestamp_plus_delta(GRANT_PROPOSAL_TIMER_SECONDS),
                threshold=LAZY_CONSENSUS_THRESHOLD,
                reaction=CANCEL_EMOJI_UNICODE,
                voting_link=voting_message.jump_url,
            )
        )
        logger.info(
            "Sent confirmation messages for grant proposal with message_id=%d", ctx.message.id
        )

        # Add grant proposal to dictionary and database, including the message id in the voting channel sent above
        new_grant_proposal = GrantProposals(
            message_id=ctx.message.id,
            channel_id=ctx.message.channel.id,
            author=ctx.message.author.mention,
            voting_message_id=voting_message.id,
            mention=mention,
            amount=amount,
            description=description,
            timer=0,
            bot_response_message_id=bot_response_message.id,
        )
        add_grant_proposal(new_grant_proposal)

        # Run the approval coroutine
        client.loop.create_task(approve_grant_proposal(ctx.message.id))
        logger.info("Added task to event loop to approve message_id=%d", message.id)

    except Exception as e:
        try:
            # Try replying in Discord
            await ctx.message.reply(
                f"An unexpected error occurred when adding proposal. cc {RESPONSIBLE_MENTION}"
            )
        except Exception as e:
            logger.critical("Unable to reply in the chat that a critical error has occurred.")

        logger.critical(
            "Unexpected error in %s while adding proposal, channel=%s, message=%s, user=%s",
            __name__,
            ctx.message.channel.id,
            ctx.message.id,
            ctx.message.author.mention,
            exc_info=True,
        )
