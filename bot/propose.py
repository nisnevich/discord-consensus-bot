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


async def submit_proposal(ctx, description, finance_recipients=None):
    # FIXME fix validation
    if finance_recipients:
        # Validity checks
        if not await validate_grantless_message(ctx.message, description):
            return
        # Add proposal to the voting channel
        voting_channel_text = NEW_GRANTLESS_PROPOSAL_VOTING_CHANNEL_MESSAGE.format(
            countdown=get_discord_countdown_plus_delta(PROPOSAL_DURATION_SECONDS),
            author=ctx.message.author.mention,
            description=description,
        )
        # Reply to the proposer if the message is not send in the voting channel (to avoid flooding)
        proposer_response_text = NEW_GRANTLESS_PROPOSAL_RESPONSE.format(
            voting_link=voting_message.jump_url,
        )
    else:
        # Validity checks
        if not await validate_grant_message(ctx.message, mention, amount, description):
            return
        # Compose voting channel message
        voting_channel_text = NEW_GRANT_PROPOSAL_VOTING_CHANNEL_MESSAGE.format(
            amount_reaction=NEW_PROPOSAL_WITH_GRANT_AMOUNT_REACTION(amount),
            author=ctx.message.author.mention,
            countdown=get_discord_countdown_plus_delta(PROPOSAL_DURATION_SECONDS),
            amount_sum=get_amount_to_print(amount),
            description=description,
        )
        # Compose reply to the proposer
        proposer_response_text = NEW_GRANT_PROPOSAL_RESPONSE.format(
            voting_link=voting_message.jump_url,
        )

    # Send proposal to the voting channel
    voting_channel = client.get_channel(VOTING_CHANNEL_ID)
    voting_message = await voting_channel.send(voting_channel_text)

    # Reply to the proposer (if the message was send in a channel other than voting, to avoid flooding there)
    bot_response_message = None
    if voting_channel.id != ctx.message.channel.id:
        bot_response_message = await ctx.message.reply(proposer_response_text)
    logger.info(
        "Sent confirmation messages for %s proposal with message_id=%d",
        "grantless" if finance_recipients else "grant",
        ctx.message.id,
    )

    # Add grant proposal to dictionary and database, including the message id in the voting channel sent above
    new_proposal = Proposals(
        message_id=ctx.message.id,
        channel_id=ctx.message.channel.id,
        author_id=ctx.message.author.id,
        voting_message_id=voting_message.id,
        not_financial=True if finance_recipients else False,
        description=description,
        # set the datetimes in UTC, to preserve a single timezone for calculations
        submitted_at=datetime.utcnow(),
        closed_at=datetime.utcnow() + timedelta(seconds=PROPOSAL_DURATION_SECONDS),
        bot_response_message_id=bot_response_message.id if bot_response_message else 0,
        threshold_negative=LAZY_CONSENSUS_THRESHOLD_NEGATIVE,
        threshold_positive=FULL_CONSENSUS_THRESHOLD_POSITIVE
        if FULL_CONSENSUS_ENABLED
        else THRESHOLD_DISABLED_DB_VALUE,
        finance_recipients=finance_recipients,
    )
    await add_proposal(new_proposal, db)

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
        logger.debug("Proposal received: %s", ctx.message.content)

        # A reserve mechanism to stop accepting new proposals - if a certain file exists, reply and exit
        if os.path.exists(STOP_ACCEPTING_PROPOSALS_FLAG_FILE_NAME):
            await ctx.message.reply(PROPOSALS_PAUSED_RESPONSE)
            logger.info(
                "Rejecting the proposal from %s because a stopcock file is detected.",
                ctx.message.author.mention,
            )
            return
        # Don't accept proposal if recovery is in progress - reply and exit
        if db.is_recovery():
            await ctx.message.reply(PROPOSALS_PAUSED_RECOVERY_RESPONSE)
            logger.info(
                "Rejecting the proposal from %s because recovery is in progress.",
                ctx.message.author.mention,
            )
            return
        # Validate that the user is allowed to use the command
        if not await validate_roles(ctx.message.author):
            await ctx.message.reply(ERROR_MESSAGE_INVALID_ROLE)
            logger.info("Unauthorized user. message_id=%d", ctx.message.id)
            return

        # Retrieve the proposal description (any text that follows the command name)
        match_description = re.search(
            rf"^\{DISCORD_COMMAND_PREFIX}\S+\s+([\w\W]+)$", ctx.message.content
        )
        # If the description isn't found, reply with an error and exit
        if not match_description:
            await ctx.message.reply(ERROR_MESSAGE_INVALID_COMMAND_FORMAT)
            logger.info(
                "Invalid command format. message_id=%d, invalid value=%s",
                ctx.message.id,
                ctx.message.content,
            )
            return
        # Retrieve the description
        description = match_description.group(1)
        # Parse all statements in the description where one or more mentions are followed by a number (mention in discord api is <@id>, e.g.<@1234567890>; floating point separator is '.')
        match_recipients = re.finditer(r"\w*\s*((?:<@\d+>\s*)+)([\.\d]+)\w*\s*", description)
        # If recipients mentions and amount are found, it's a grant proposal
        if match_recipients:
            finance_recipients = []
            # Iterate over the matches
            for match in match_recipients:
                # Extract recipient_ids and amount from the match object
                recipient_ids = match.group(1).replace('<', '').replace('>', '').replace('@', '')
                amount = float(match.group(2))
                # Create a new FinanceRecipients instance and populate it
                recipient = Grantrecipients(recipient_ids=recipient_ids, amount=amount)
                # Add the new FinanceRecipients instance to a list
                finance_recipients.append(recipient)
            # Submit the financial proposal
            await submit_proposal(ctx, description, finance_recipients=finance_recipients)
        else:
            # Submit the simple proposal
            await submit_proposal(ctx, description)

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
