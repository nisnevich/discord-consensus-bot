import asyncio
import logging
import typing
import discord
import re
import os
from discord.ext import commands
from datetime import datetime, timedelta

from bot.grant import grant
from bot.config.const import *
from bot.utils.db_utils import DBUtil
from bot.utils.proposal_utils import (
    get_proposal,
    add_proposal,
    is_relevant_proposal,
    get_voters_with_vote,
)
from bot.config.logging_config import log_handler, console_handler
from bot.utils.validation import validate_roles, validate_grant_message, validate_grantless_message
from bot.utils.discord_utils import get_discord_client, get_message
from bot.utils.formatting_utils import (
    get_discord_timestamp_plus_delta,
    get_discord_countdown_plus_delta,
    get_amount_to_print,
)
from bot.config.schemas import Proposals
from bot.vote import cancel_proposal

logger = logging.getLogger(__name__)
logger.setLevel(DEFAULT_LOG_LEVEL)
logger.addHandler(log_handler)
logger.addHandler(console_handler)

db = DBUtil()
client = get_discord_client()


async def approve_proposal(voting_message_id):
    """
    A coroutine that approves a proposal by checking if the time to approve has come and if the proposal hasn't been cancelled.
    """
    logger.info("Running approval coroutine for voting_message_id=%d", voting_message_id)
    try:
        proposal = get_proposal(voting_message_id)
    except ValueError as e:
        logger.error(f"Error while getting grant proposal: {e}")
        return
    # Unless the timer runs out, sleep (any other operations in this cycle should be minimised, as it runs every 5-10 sec for each active proposal)
    while proposal.closed_at > datetime.utcnow():
        # If proposal was cancelled, it will be removed from dictionary (see on_raw_reaction_add),
        # so we should exit
        if not is_relevant_proposal(voting_message_id):
            return
        # Sleep until the next check
        await asyncio.sleep(APPROVAL_SLEEP_SECONDS)
    try:
        # When the time has come, double check to make sure the proposal wasn't cancelled
        if not is_relevant_proposal(voting_message_id):
            return
        # If full consensus is enabled for this proposal, and the minimal number of supporting votes is not reached, cancel the proposal
        if (
            proposal.threshold_positive != THRESHOLD_DISABLED_DB_VALUE
            and len(get_voters_with_vote(proposal, Vote.YES)) < proposal.threshold_positive
        ):
            # Retrieve the voting message
            voting_message = await get_message(client, VOTING_CHANNEL_ID, voting_message_id)
            # Cancel the proposal
            await cancel_proposal(
                proposal,
                ProposalResult.CANCELLED_BY_NOT_REACHING_POSITIVE_THRESHOLD,
                voting_message,
            )

        # Apply the grant
        await grant(voting_message_id)
    except ValueError as e:
        logger.error(f"Error while removing grant proposal: {e}")


async def proposal_with_grant(ctx, original_message, mention, amount, description):
    # Validity checks
    if not await validate_grant_message(original_message, mention, amount, description):
        return

    # Add proposal to the voting channel
    voting_channel = client.get_channel(VOTING_CHANNEL_ID)
    voting_message = await voting_channel.send(
        NEW_GRANT_PROPOSAL_VOTING_CHANNEL_MESSAGE.format(
            amount_reaction=NEW_PROPOSAL_WITH_GRANT_AMOUNT_REACTION(amount),
            author=ctx.message.author.mention,
            countdown=get_discord_countdown_plus_delta(PROPOSAL_DURATION_SECONDS),
            amount=get_amount_to_print(amount),
            mention=mention.mention,
            description=description,
        )
    )

    # Reply to the proposer if the message is not send in the voting channel (to avoid flooding)
    bot_response_message = None
    if voting_channel.id != ctx.message.channel.id:
        bot_response_message = await original_message.reply(
            NEW_GRANT_PROPOSAL_RESPONSE.format(
                amount=get_amount_to_print(amount),
                mention=mention.mention,
                voting_link=voting_message.jump_url,
            )
        )
    logger.info("Sent confirmation messages for proposal with grant, message_id=%d", ctx.message.id)

    # Add grant proposal to dictionary and database, including the message id in the voting channel sent above
    new_grant_proposal = Proposals(
        message_id=ctx.message.id,
        channel_id=ctx.message.channel.id,
        author=ctx.message.author.id,
        voting_message_id=voting_message.id,
        is_grantless=False,
        mention=mention.mention,
        amount=amount,
        description=description,
        # set the datetimes in UTC, to preserve a single timezone for calculations
        submitted_at=datetime.utcnow(),
        closed_at=datetime.utcnow() + timedelta(seconds=PROPOSAL_DURATION_SECONDS),
        bot_response_message_id=bot_response_message.id if bot_response_message else 0,
        threshold=LAZY_CONSENSUS_THRESHOLD_NEGATIVE,
        threshold_positive=FULL_CONSENSUS_THRESHOLD_POSITIVE
        if FULL_CONSENSUS_ENABLED
        else THRESHOLD_DISABLED_DB_VALUE,
    )
    await add_proposal(new_grant_proposal, db)

    # Add tick and cross reactions to the voting message after adding proposal to DB
    if FULL_CONSENSUS_ENABLED:
        await voting_message.add_reaction(EMOJI_VOTING_YES)
        await voting_message.add_reaction(EMOJI_VOTING_NO)

    # Run the approval coroutine
    client.loop.create_task(approve_proposal(voting_message.id))
    logger.info("Added task to event loop to approve message_id=%d", voting_message.id)


async def proposal_grantless(ctx, original_message, description):
    # Validity checks
    if not await validate_grantless_message(original_message, description):
        return

    # Add proposal to the voting channel
    voting_channel = client.get_channel(VOTING_CHANNEL_ID)
    voting_message = await voting_channel.send(
        NEW_GRANTLESS_PROPOSAL_VOTING_CHANNEL_MESSAGE.format(
            countdown=get_discord_countdown_plus_delta(PROPOSAL_DURATION_SECONDS),
            author=ctx.message.author.mention,
            description=description,
        )
    )

    # Reply to the proposer if the message is not send in the voting channel (to avoid flooding)
    bot_response_message = None
    if voting_channel.id != ctx.message.channel.id:
        bot_response_message = await original_message.reply(
            NEW_GRANTLESS_PROPOSAL_RESPONSE.format(
                voting_link=voting_message.jump_url,
            )
        )
    logger.info(
        "Sent confirmation messages for grantless proposal with message_id=%d", ctx.message.id
    )

    # Add grant proposal to dictionary and database, including the message id in the voting channel sent above
    new_grant_proposal = Proposals(
        message_id=ctx.message.id,
        channel_id=ctx.message.channel.id,
        author=ctx.message.author.id,
        voting_message_id=voting_message.id,
        is_grantless=True,
        mention=None,
        amount=None,
        description=description,
        # set the datetimes in UTC, to preserve a single timezone for calculations
        submitted_at=datetime.utcnow(),
        closed_at=datetime.utcnow() + timedelta(seconds=PROPOSAL_DURATION_SECONDS),
        bot_response_message_id=bot_response_message.id if bot_response_message else 0,
        threshold=LAZY_CONSENSUS_THRESHOLD_NEGATIVE,
        threshold_positive=FULL_CONSENSUS_THRESHOLD_POSITIVE
        if FULL_CONSENSUS_ENABLED
        else THRESHOLD_DISABLED_DB_VALUE,
    )
    await add_proposal(new_grant_proposal, db)

    # Add tick and cross reactions to the voting message after adding proposal to DB
    if FULL_CONSENSUS_ENABLED:
        await voting_message.add_reaction(EMOJI_VOTING_YES)
        await voting_message.add_reaction(EMOJI_VOTING_NO)

    # Run the approval coroutine
    client.loop.create_task(approve_proposal(voting_message.id))
    logger.info("Added task to event loop to approve message_id=%d", voting_message.id)


@client.command(name=GRANT_PROPOSAL_COMMAND_NAME, aliases=PROPOSAL_COMMAND_ALIASES)
async def propose_command(ctx, *args):
    f"""
    Submit a grant proposal. The proposal will be approved after {PROPOSAL_DURATION_SECONDS}
    seconds unless {LAZY_CONSENSUS_THRESHOLD_NEGATIVE} members with {ROLE_IDS_ALLOWED} roles react with
    {EMOJI_VOTING_NO} emoji to the proposal message which will be posted by the bot in the
    {VOTING_CHANNEL_ID} channel.
    Parameters:
        ctx (commands.Context): The context in which the command was called.
        args: The description of grant being proposed. It may include "mention" and "amount", or it can be a grantless proposal. These two are distinguished as simply as:
            1) If the first argument is a mention of a discord user - consider it a grant proposal (and validate accordingly)
            2) If it doesn't start with a mention - consider it grantless
    """

    try:
        # Get the entire message content
        message_content = ctx.message.content
        logger.debug("Proposal received: %s", message_content)

        original_message = await ctx.fetch_message(ctx.message.id)

        # A reserve mechanism to stop accepting new proposals
        if os.path.exists(STOP_ACCEPTING_PROPOSALS_FLAG_FILE_NAME):
            await original_message.add_reaction(REACTION_GREETINGS)
            await original_message.reply(PROPOSALS_PAUSED_RESPONSE)
            logger.info(
                "Rejecting the proposal from %s because a stopcock file is detected.",
                ctx.message.author.mention,
            )
            return

        # Don't accept proposal if recovery is in progress
        if db.is_recovery():
            await original_message.add_reaction(REACTION_GREETINGS)
            await original_message.reply(PROPOSALS_PAUSED_RECOVERY_RESPONSE)
            logger.info(
                "Rejecting the proposal from %s because recovery is in progress.",
                ctx.message.author.mention,
            )
            return

        # Validate that the user is allowed to use the command
        if not await validate_roles(ctx.message.author):
            await original_message.add_reaction(REACTION_GREETINGS)
            await original_message.reply(ERROR_MESSAGE_INVALID_ROLE)
            logger.info("Unauthorized user. message_id=%d", original_message.id)
            return

        # Less than 3 args means the input is certainly wrong (mention, amount, and some description of the grant is required)
        if len(args) < 3:
            await original_message.add_reaction(REACTION_GREETINGS)
            await original_message.reply(ERROR_MESSAGE_INVALID_COMMAND_FORMAT)
            logger.info(
                "Invalid command format. message_id=%d, invalid value=%s",
                original_message.id,
                original_message.content,
            )
            return

        is_grantless = True
        # If there are no mentions, consider grantless, otherwise check if it looks like grant request
        if original_message.mentions:
            # If the first argument is a mention of a discord user - consider it a grant proposal (and validate accordingly), otherwise grantless
            mention = original_message.mentions[0]
            # Converting mention to <@123> format, because in the arguments it's passed like that
            mention_id_str = "<@{}>".format(mention.id)
            if args[0] == mention_id_str:
                is_grantless = False
                logger.debug("Received a proposal with a grant.")
                # Suppose that the amount follows mention, and the description follows amount; the validation of these values comes next
                amount = args[1]
                try:
                    amount = float(amount)
                except ValueError:
                    await original_message.reply(ERROR_MESSAGE_INVALID_AMOUNT)
                    logger.info(
                        "Unable to extract amount from the args. message_id=%d, invalid value=%s",
                        original_message.id,
                        amount,
                    )
                    return

                # Retrieve description including line breaks. Regex skips 3 words and one or more spaces after each of them (command name, mention amount), and takes everything else
                match = re.search(r"^\!\S+\s+\S+\s+\S+\s+([\w\W]+)$", message_content)
                if not match:
                    await original_message.reply(ERROR_MESSAGE_INVALID_AMOUNT)
                    logger.critical(
                        "Can't retrieve description from a proposal while it should be there."
                    )
                    return
                description = match.group(1)

                # Process the proposal
                await proposal_with_grant(ctx, original_message, mention, amount, description)

        if is_grantless:
            logger.debug("Received a grantless proposal.")

            # Retrieve description. Regex skips a word and one or more spaces (command name), and takes everything else
            match = re.search(r"^\!\S+\s+([\w\W]+)$", message_content)
            if not match:
                await original_message.reply(ERROR_MESSAGE_INVALID_AMOUNT)
                logger.critical(
                    "Can't retrieve description from a proposal while it should be there."
                )
                return
            description = match.group(1)

            # Process the grantless proposal
            await proposal_grantless(ctx, original_message, description)

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
            ctx.message.channel.id if ctx.message.channel else None,
            ctx.message.id,
            ctx.message.author.mention,
            exc_info=True,
        )
