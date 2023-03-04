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
)
from bot.config.logging_config import log_handler, console_handler
from bot.utils.validation import validate_roles, validate_grant_message, validate_grantless_message
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


async def send_transaction(ctx, mentions, amount, description):
    # Check if member is in DB, otherwise add it
    author_id = str(ctx.author.id)
    author_balance = session.query(FreeFundingBalance).filter_by(author=author_id).first()
    if not author_balance:
        author_balance = FreeFundingBalance(author=author_id, balance=1000)
        session.add(author_balance)
        session.commit()

    # Check if transaction can be sent, otherwise reply to user and return
    if not mentions:
        await ctx.send("Please mention at least one user to send funds to.")
        return

    if len(mentions) > 5:
        await ctx.send("You can only send funds to up to 5 users at once.")
        return

    total_amount = float(amount) * len(mentions)
    if total_amount > author_balance.balance:
        await ctx.send("You do not have enough funds to send this transaction.")
        return

    # Send transaction and substitute from DB
    transaction_time = datetime.now()
    for mention in mentions:
        mention_id = mention.strip("<@!>")
        recipient_balance = session.query(FreeFundingBalance).filter_by(author=mention_id).first()
        if not recipient_balance:
            recipient_balance = FreeFundingBalance(author=mention_id, balance=0)
            session.add(recipient_balance)

        recipient_balance.balance += float(amount)
        author_balance.balance -= float(amount)

        # Add transaction to history
        transaction = FreeFundingTransaction(
            author=author_id,
            mention=mention,
            amount=float(amount),
            description=description,
            submitted_at=transaction_time,
        )
        session.add(transaction)

    session.commit()
    await ctx.send(
        f"Transaction successful. {total_amount:.2f} points were sent to {len(mentions)} users."
    )


@client.command(name=FREE_FUNDING_COMMAND_NAME, aliases=FREE_FUNDING_COMMAND_ALIASES)
async def free_funding_transact_command(ctx, *args):
    f"""
    This method validates and processes a received free funding transaction command from a Discord user, which should include the mentioned recipient(s), amount, and a description. If the command format is invalid, or if the user is unauthorized, or if the recovery is in progress or if the free funding feature is paused, it replies with an appropriate error message. Otherwise, it extracts the mentioned recipients, amount, and description from the command and passes them to the send_transaction() method for processing.
    """

    try:
        # Get the entire message content
        message_content = ctx.message.content
        logger.debug("Transaction received: %s", message_content)

        original_message = await ctx.fetch_message(ctx.message.id)

        # A reserve mechanism to stop accepting transactions
        if os.path.exists(STOP_ACCEPTING_FREE_FUNDING_TRANSACTIONS_FLAG_FILE_NAME):
            await original_message.reply(FREE_FUNDING_PAUSED_RESPONSE)
            logger.info(
                "Rejecting the transaction from %s because a stopcock file is detected.",
                ctx.message.author.mention,
            )
            return

        # Don't accept transactions if recovery is in progress
        if db.is_recovery():
            await original_message.reply(FREE_FUNDING_PAUSED_RECOVERY_RESPONSE)
            logger.info(
                "Rejecting the transaction from %s because recovery is in progress.",
                ctx.message.author.mention,
            )
            return

        # Validate that the user is allowed to use the command
        if not await validate_roles(ctx.message.author):
            await original_message.reply(ERROR_MESSAGE_INVALID_ROLE)
            logger.info("Unauthorized user. message_id=%d", original_message.id)
            return

        # Less than 3 args means the input is certainly wrong (mention, amount, and some description of the transaction is required)
        if len(args) < 3:
            await original_message.reply(ERROR_MESSAGE_FREE_FUNDING_INVALID_COMMAND_FORMAT)
            logger.info(
                "Invalid command format. message_id=%d, invalid value=%s",
                original_message.id,
                original_message.content,
            )
            return

        if original_message.mentions:
            # The regex captures a command format that starts with DISCORD_COMMAND_PREFIX, followed by a word (command name) - "^{DISCORD_COMMAND_PREFIX}\w+\s+", followed by one or more <@userid> mentions separated by whitespace - ((?:<@\d+>\s+)+), followed by a numerical value (amount, may include dots as floating separators) - ([\d\.]+), and ends with any remaining characters (description) - ([\w\W]+)
            match = re.search(
                rf"^{DISCORD_COMMAND_PREFIX}\w+\s+((?:<@\d+>\s+)+)([\d\.]+)\s+([\w\W]+)$",
                message_content,
            )
            if not match:
                await original_message.reply(ERROR_MESSAGE_FREE_FUNDING_INVALID_COMMAND_FORMAT)
                logger.info(
                    "Invalid command format. message_id=%d, invalid value=%s",
                    original_message.id,
                    original_message.content,
                )
                return

            mentions = " ".split(match.group(1))
            amount = match.group(2)
            description = match.group(3)

            send_transaction(ctx, mentions, amount, description)

    except Exception as e:
        try:
            # Try replying in Discord
            await ctx.message.reply(
                f"An unexpected error occurred during transaction. cc {RESPONSIBLE_MENTION}"
            )
        except Exception as e:
            logger.critical("Unable to reply in the chat that a critical error has occurred.")

        logger.critical(
            "Unexpected error in %s during transaction, channel=%s, message=%s, user=%s",
            __name__,
            ctx.message.channel.id if ctx.message.channel else None,
            ctx.message.id,
            ctx.message.author.mention,
            exc_info=True,
        )
