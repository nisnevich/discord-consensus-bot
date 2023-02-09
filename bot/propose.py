import asyncio
import logging
import typing
import discord
from discord.ext import commands

from bot.grant import grant
from bot.config.const import *
from bot.utils.db_utils import DBUtil
from bot.utils.proposal_utils import (
    get_proposal,
    add_proposal,
    is_relevant_proposal,
)
from bot.config.logging_config import log_handler, console_handler
from bot.utils.validation import validate_roles, validate_grant_message
from bot.utils.discord_utils import get_discord_client
from bot.utils.formatting_utils import (
    get_discord_timestamp_plus_delta,
    get_discord_countdown_plus_delta,
    get_amount_to_print,
)
from bot.config.schemas import Proposals

logger = logging.getLogger(__name__)
logger.setLevel(DEFAULT_LOG_LEVEL)
logger.addHandler(log_handler)
logger.addHandler(console_handler)

db = DBUtil()
client = get_discord_client()


async def approve_proposal(voting_message_id):
    """
    Loop until the timer reaches GRANT_PROPOSAL_TIMER_SECONDS days. Every minute, the timer is incremented by 60 seconds and updated in the database. If the timer ends, the grant proposal is approved and the entry is removed from the dictionary and database.
    """
    logger.info("Running approval coroutine for voting_message_id=%d", voting_message_id)
    try:
        grant_proposal = get_proposal(voting_message_id)
    except ValueError as e:
        logger.error(f"Error while getting grant proposal: {e}")
        return
    while grant_proposal.timer < GRANT_PROPOSAL_TIMER_SECONDS:
        # If proposal was cancelled, it will be removed from dictionary (see on_raw_reaction_add)
        if not is_relevant_proposal(voting_message_id):
            return
        await asyncio.sleep(GRANT_PROPOSAL_TIMER_SLEEP_SECONDS)
        grant_proposal.timer += GRANT_PROPOSAL_TIMER_SLEEP_SECONDS
        await db.commit()
    try:
        # Double check to make sure proposal wasn't cancelled
        if not is_relevant_proposal(voting_message_id):
            return
        await grant(voting_message_id)
    except ValueError as e:
        logger.error(f"Error while removing grant proposal: {e}")


async def proposal_with_grant(ctx, original_message, mention, args):

    # TODO parse amount and description
    amount = 10.0
    description = "test"

    # Validity checks
    if not await validate_roles(ctx.message.author):
        await original_message.reply(ERROR_MESSAGE_INVALID_ROLE)
        logger.info("Unauthorized user. message_id=%d", original_message.id)
        return
    if not await validate_grant_message(original_message, amount, description):
        return
    if not mention or not amount or not description:
        await original_message.reply(
            COMMAND_FORMAT_RESPONSE.format(author=ctx.message.author.mention)
        )
        return

    # Add proposal to the voting channel
    voting_channel = client.get_channel(VOTING_CHANNEL_ID)
    voting_message = await voting_channel.send(
        NEW_PROPOSAL_VOTING_CHANNEL_MESSAGE.format(
            countdown=get_discord_countdown_plus_delta(GRANT_PROPOSAL_TIMER_SECONDS),
            date_finish=get_discord_timestamp_plus_delta(GRANT_PROPOSAL_TIMER_SECONDS),
            amount=get_amount_to_print(amount),
            mention=mention.mention,
            author=ctx.message.author.mention,
            threshold=LAZY_CONSENSUS_THRESHOLD,
            reaction=CANCEL_EMOJI_UNICODE,
            description=description,
        )
    )

    # Reply to the proposer if the message is not send in the voting channel (to avoid unnecessary spam otherwise)
    bot_response_message = None
    if voting_channel.id != ctx.message.channel.id:
        bot_response_message = await original_message.reply(
            NEW_PROPOSAL_SAME_CHANNEL_RESPONSE.format(
                author=ctx.message.author.mention,
                mention=mention.mention,
                amount=get_amount_to_print(amount),
                threshold=LAZY_CONSENSUS_THRESHOLD,
                reaction=CANCEL_EMOJI_UNICODE,
                voting_link=voting_message.jump_url,
            )
        )
    logger.info("Sent confirmation messages for grant proposal with message_id=%d", ctx.message.id)

    # Add grant proposal to dictionary and database, including the message id in the voting channel sent above
    new_grant_proposal = Proposals(
        message_id=ctx.message.id,
        channel_id=ctx.message.channel.id,
        author=ctx.message.author.mention,
        voting_message_id=voting_message.id,
        is_grantless=False,
        mention=mention.mention,
        amount=amount,
        description=description,
        timer=0,
        bot_response_message_id=bot_response_message.id if bot_response_message else 0,
    )
    await add_proposal(new_grant_proposal, db)

    # Run the approval coroutine
    client.loop.create_task(approve_proposal(voting_message.id))
    logger.info("Added task to event loop to approve message_id=%d", voting_message.id)


async def proposal_grantless(ctx, original_message, description):
    pass


@client.command(name=GRANT_PROPOSAL_COMMAND_NAME)
async def propose_command(ctx, *args):
    f"""
    Submit a grant proposal. The proposal will be approved after {GRANT_PROPOSAL_TIMER_SECONDS}
    seconds unless {LAZY_CONSENSUS_THRESHOLD} members with {ROLE_IDS_ALLOWED} roles react with
    {CANCEL_EMOJI_UNICODE} emoji to the proposal message which will be posted by the bot in the
    {VOTING_CHANNEL_ID} channel.
    Parameters:
        ctx (commands.Context): The context in which the command was called.
        args: The description of grant being proposed. It may include "mention" and "amount", or it can be a grantless proposal. These two are distinguished as simply as:
            1) If the first argument is a mention of a discord user - consider it a grant proposal (and validate accordingly)
            2) If it doesn't start with a mention - consider it grantless
    """

    try:
        original_message = await ctx.fetch_message(ctx.message.id)
        full_text = " ".join(args)

        if len(args) < 3:
            await original_message.reply("Too short proposal")
            logger.info("The proposal is less than 3 args long. message_id=%d", original_message.id)
            return

        is_grantless = True
        if original_message.mentions:
            # If the first argument is a mention of a discord user - consider it a grant proposal (and validate accordingly)
            mention = original_message.mentions[0]
            # Converting mention to <@123> format, because in the arguments it's passed like that
            mention_id_str = "<@{}>".format(mention.id)
            if args[0] == mention_id_str:
                is_grantless = False
                logger.debug("Received a proposal with a grant.")
                await proposal_with_grant(ctx, original_message, mention, args)

        if is_grantless:
            logger.debug("Received a grantless proposal.")
            await proposal_grantless(ctx, original_message, full_text)

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
