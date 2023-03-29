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
    add_finance_recipient,
    proposal_lock,
)
from bot.config.logging_config import log_handler, console_handler
from bot.utils.validation import (
    validate_roles,
    validate_financial_proposal,
    validate_not_financial_proposal,
)
from bot.utils.discord_utils import get_discord_client, get_message
from bot.utils.formatting_utils import (
    get_discord_timestamp_plus_delta,
    get_discord_countdown_plus_delta,
    get_amount_to_print,
    get_nickname_by_id_or_mention,
)
from bot.config.schemas import Proposals, FinanceRecipients
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
        # Acquire the proposal lock when accepting or cancelling to avoid concurrency errors
        async with proposal_lock:
            # Double check to make sure the proposal wasn't accepted or cancelled while the lock was acquired by other thread
            if not is_relevant_proposal(voting_message_id):
                logger.info(
                    "Proposal became irrelevant while waiting for a lock to accept the proposal (or cancel it by not reaching enough support)."
                )
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
                return
            # Apply the grant
            await grant(voting_message_id)

    except ValueError as e:
        logger.error(f"Error while removing grant proposal: {e}")


async def submit_proposal(
    ctx,
    proposal_voting_type: ProposalVotingType,
    proposal_voting_anonymity_type: ProposalVotingAnonymityType,
    description,
    finance_recipients=None,
    total_amount=None,
):
    f"""
    Submit a proposal. The proposal will be approved after {PROPOSAL_DURATION_SECONDS}
    seconds unless {LAZY_CONSENSUS_THRESHOLD_NEGATIVE} members with {ROLE_IDS_ALLOWED} roles react with
    {EMOJI_VOTING_NO} emoji to the proposal message which will be posted by the bot in the
    {VOTING_CHANNEL_ID} channel. Also, if FULL_CONSENSUS_ENABLED is True, the reactions
    EMOJI_VOTING_YES and EMOJI_VOTING_NO will appear below the voting message, and the proposal will
    need to have at least FULL_CONSENSUS_THRESHOLD_POSITIVE supporting votes in order to pass.
    Parameters:
        ctx (commands.Context): The context in which the command was called.
        proposal_voting_type: Value from ProposalVotingType, whether the proposal is binary (yes or
        no), multichoice or something else.
        proposal_voting_anonymity_type: Value from ProposalVotingAnonymityType, whether the voters will
        be opened, or will be revealed after the proposal timer will finish.
        description: The text description of a proposal given by the proposer.
        finance_recipients: If a proposal has a grant, a list of FinanceRecipients objects parsed
        from the proposal text, otherwise None.
        total_amount: If a proposal has a grant, a total amount determined by summing up all
        recipients multiplied by the amount to give to each, otherwise None.
    """
    if not finance_recipients:
        # Validity checks
        if not await validate_not_financial_proposal(ctx.message, description):
            return
        # Add proposal to the voting channel
        voting_channel_text = NEW_GRANTLESS_PROPOSAL_VOTING_CHANNEL_MESSAGE.format(
            author=ctx.message.author.mention,
            anonymity=OPENED_VOTING_CHANNEL_EDIT
            if proposal_voting_anonymity_type == ProposalVotingAnonymityType.OPENED
            else REVEAL_VOTERS_AT_THE_END_VOTING_CHANNEL_EDIT,
            countdown=get_discord_countdown_plus_delta(PROPOSAL_DURATION_SECONDS),
            description=description,
        )
        # Send proposal to the voting channel
        voting_channel = client.get_channel(VOTING_CHANNEL_ID)
        voting_message = await voting_channel.send(voting_channel_text)
        # Reply to the proposer if the message is not send in the voting channel (to avoid flooding)
        proposer_response_text = NEW_GRANTLESS_PROPOSAL_RESPONSE.format(
            voting_link=voting_message.jump_url,
        )
    else:
        # Validity checks
        if not await validate_financial_proposal(
            ctx.message, description, finance_recipients, total_amount
        ):
            return
        # Compose voting channel message
        voting_channel_text = NEW_GRANT_PROPOSAL_VOTING_CHANNEL_MESSAGE.format(
            amount_reaction=NEW_PROPOSAL_WITH_GRANT_AMOUNT_REACTION(total_amount),
            author=ctx.message.author.mention,
            anonymity=OPENED_VOTING_CHANNEL_EDIT
            if proposal_voting_anonymity_type == ProposalVotingAnonymityType.OPENED
            else REVEAL_VOTERS_AT_THE_END_VOTING_CHANNEL_EDIT,
            countdown=get_discord_countdown_plus_delta(PROPOSAL_DURATION_SECONDS),
            amount_sum=get_amount_to_print(total_amount),
            description=description,
        )
        # Send proposal to the voting channel
        voting_channel = client.get_channel(VOTING_CHANNEL_ID)
        voting_message = await voting_channel.send(voting_channel_text)
        # Compose reply to the proposer
        proposer_response_text = NEW_GRANT_PROPOSAL_RESPONSE.format(
            voting_link=voting_message.jump_url,
        )

    # Reply to the proposer (if the message was send in a channel other than voting, to avoid flooding there)
    bot_response_message = None
    if voting_channel.id != ctx.message.channel.id:
        bot_response_message = await ctx.message.reply(proposer_response_text)
    logger.info(
        "Sent confirmation messages for %s proposal with message_id=%d",
        "grantless" if finance_recipients else "grant",
        ctx.message.id,
    )

    # Create a proposal
    new_proposal = Proposals(
        message_id=ctx.message.id,
        channel_id=ctx.message.channel.id,
        author_id=ctx.message.author.id,
        voting_message_id=voting_message.id,
        description=description,
        # set the datetimes in UTC, to preserve a single timezone for calculations
        submitted_at=datetime.utcnow(),
        closed_at=datetime.utcnow() + timedelta(seconds=PROPOSAL_DURATION_SECONDS),
        bot_response_message_id=bot_response_message.id if bot_response_message else 0,
        not_financial=False if finance_recipients else True,
        total_amount=total_amount,
        threshold_negative=LAZY_CONSENSUS_THRESHOLD_NEGATIVE,
        threshold_positive=FULL_CONSENSUS_THRESHOLD_POSITIVE
        if FULL_CONSENSUS_ENABLED
        else THRESHOLD_DISABLED_DB_VALUE,
        proposal_type=proposal_voting_type.value,
        anonymity_type=proposal_voting_anonymity_type.value,
    )
    # Add proposal to DB
    await add_proposal(new_proposal, db)
    # Add recipients to the proposal in DB
    for recipient in finance_recipients:
        recipient.proposal_id = new_proposal.id
        await add_finance_recipient(new_proposal, recipient)

    # Add tick and cross reactions to the voting message after adding proposal to DB
    if FULL_CONSENSUS_ENABLED:
        await voting_message.add_reaction(EMOJI_VOTING_YES)
        await voting_message.add_reaction(EMOJI_VOTING_NO)

    # Run the approval coroutine
    client.loop.create_task(approve_proposal(voting_message.id))
    logger.info("Added task to event loop to approve message_id=%d", voting_message.id)


async def parse_propose_command(ctx, proposal_voting_type, proposal_voting_anonymity_type, *args):
    f"""
    Parses the proposal command, extracting all necessary arguments.
    Parameters:
        ctx (commands.Context): The context in which the command was called.
        proposal_voting_anonymity_type: True or False, whether the voters will be opened, or will be revealed after the
        proposal timer will finish.
        args: The description of grant being proposed. It may include "mentions" and "amount", or it
        can be a grantless proposal. If a sequence of Discord mentions followed by the amount to
        give is found, the proposal is considered with a grant, otherwise grantless. The amount can be
        an integer or a fractional number with "." separator.
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
        # Extract the description
        description = match_description.group(1)
        # Parse all statements in the description where one or more mentions are followed by a number (mention in discord api is <@id>, e.g.<@1234567890>; floating point separator is '.')
        match_recipients = re.finditer(r"\w*\s*((?:<@\d+>\s*)+)([\.\d]+)\w*\s*", description)
        # If recipients mentions and amount are found, it's a grant proposal
        if match_recipients:
            finance_recipients = []
            total_amount = 0
            # Iterate over the matches
            for match in match_recipients:
                # Extract ids from mentions
                match_recipient_ids = re.finditer(r"<@(\d+)>", match.group(1))
                ids = [id_match.group(1) for id_match in match_recipient_ids]
                # Retrieve nicknames for all users (will be used for analytics later)
                nicknames = [await get_nickname_by_id_or_mention(id) for id in ids]
                # Extract the amount to send
                amount = float(match.group(2))
                # Create a new FinanceRecipients instance and populate it
                recipient = FinanceRecipients(
                    recipient_ids=DB_ARRAY_COLUMN_SEPARATOR.join(ids),
                    recipient_nicknames=COMMA_LIST_SEPARATOR.join(nicknames),
                    amount=amount,
                )
                # Add the new FinanceRecipients instance to a list
                finance_recipients.append(recipient)
                # Add the sum to total amount
                total_amount += amount * len(ids)
            # Submit the financial proposal
            await submit_proposal(
                ctx,
                proposal_voting_type,
                proposal_voting_anonymity_type,
                description,
                finance_recipients=finance_recipients,
                total_amount=total_amount,
            )
        else:
            # Submit the simple proposal
            await submit_proposal(
                ctx,
                proposal_voting_type,
                proposal_voting_anonymity_type,
                description,
            )

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


@client.command(
    name=PROPOSAL_ANONYMOUS_VOTING_COMMAND_NAME, aliases=PROPOSAL_ANONYMOUS_VOTING_ALIASES
)
async def command_propose_anonymous_voting(ctx, *args):
    """
    Submit a proposal with anonymous voting. Votes will be hidden while the voting is active, but
    once the timer will have been completed, votes will be revealed.
    """
    await parse_propose_command(
        ctx,
        ProposalVotingType.YES_OR_NO,
        ProposalVotingAnonymityType.REVEAL_VOTERS_AT_THE_END,
        args,
    )


@client.command(name=GRANT_PROPOSAL_COMMAND_NAME, aliases=PROPOSAL_COMMAND_ALIASES)
async def command_propose_opened_voting(ctx, *args):
    """
    Submit a proposal with opened voting. All added votes will be immediately visible for all
    members (who can see the voting message itself).
    """
    await parse_propose_command(
        ctx,
        ProposalVotingType.YES_OR_NO,
        ProposalVotingAnonymityType.OPENED,
        args,
    )
