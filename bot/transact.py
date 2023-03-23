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
from bot.utils.validation import validate_roles, validate_free_transaction
from bot.utils.discord_utils import get_discord_client
from bot.utils.formatting_utils import (
    get_discord_timestamp_plus_delta,
    get_discord_countdown_plus_delta,
    get_amount_to_print,
    get_nickname_by_id_or_mention,
    get_id_by_mention,
)
from bot.config.schemas import FreeFundingBalance, FreeFundingTransaction
from bot.help import send_free_funding_balance

logger = logging.getLogger(__name__)
logger.setLevel(DEFAULT_LOG_LEVEL)
logger.addHandler(log_handler)
logger.addHandler(console_handler)

db = DBUtil()
client = get_discord_client()


@client.command(name=RESET_BALANCE_COMMAND_NAME)
async def reset_free_funding(ctx, *args):
    """
    Reset the free funding balance of the author. Used solely for testing purposes on dev/beta environments.
    """
    # Not allowing to run on the main server
    if SERVER_ENVIRONMENT == ServerEnvironment.PROD:
        await ctx.message.add_reaction(REACTION_ON_TRANSACTION_FAILED)
        await ctx.message.reply("This command isn't available on the main server.")
        return

    # Reset the free funding balance of the author
    author_id = ctx.message.author.id
    # Extract the balance
    author_balance = db.get_user_free_funding_balance(author_id)
    # Renew the balance
    author_balance.balance = FREE_FUNDING_LIMIT_PERSON_PER_SEASON
    # Reply to the user
    await ctx.message.add_reaction(REACTION_ON_TRANSACTION_SUCCEED)
    await ctx.message.reply("Your balance was reset, enjoy testing. :sunny:")
    # Commit changes to DB
    await db.save()

    logger.info("Balance reset for author_id=%s", author_id)


async def send_transaction(ctx, original_message, mentions, ids, amount, description):
    # Check if member is in DB, otherwise add it (roles should have already been checked before calling this method)
    author_mention = str(ctx.message.author.mention)
    author_balance = db.get_user_free_funding_balance(ctx.message.author.id)
    if not author_balance:
        logger.debug("Added free funding balance for author=%s", author_mention)
        author_balance = FreeFundingBalance(
            author_id=ctx.message.author.id,
            author_nickname=await get_nickname_by_id_or_mention(author_mention),
            balance=FREE_FUNDING_LIMIT_PERSON_PER_SEASON,
        )
        await db.add(author_balance)

    # Validity checks (including whether the author has sufficient funds, that's why we do it after retreiving the balance)
    if not await validate_free_transaction(
        original_message, ctx.message.author.id, author_balance, ids, amount, description
    ):
        await ctx.message.add_reaction(REACTION_ON_TRANSACTION_FAILED)
        return

    # Substitute transaction from the users balance
    author_balance.balance -= amount * len(mentions)
    await db.save()

    # Send the transaction (doing so after substracting the balance from DB gives us a bit more control, because if we first apply the grant, and then some error occurs while updating DB, we will not be able to revert the transaction since we don't control Accountant)
    grant_message = GRANT_COMMAND_FREE_FUNDING_MESSAGE.format(
        prefix=DISCORD_COMMAND_PREFIX,
        grant_command=GRANT_APPLY_COMMAND_NAME,
        mentions=" ".join(mentions),
        amount=get_amount_to_print(amount),
        description=description,
        author=author_mention,
        balance=get_amount_to_print(author_balance.balance),
        tips_url=original_message.jump_url,
    )
    try:
        channel = client.get_channel(GRANT_APPLY_CHANNEL_ID)
        grant_message = await channel.send(grant_message)
        # Remove embeds
        await grant_message.edit(suppress=True)
    except Exception as e:
        await ctx.message.channel.send(
            f"Could not apply grant. cc {RESPONSIBLE_MENTION}",
        )
        logger.critical(
            "An error occurred while sending grant message, message_id=%d",
            original_message.id,
            exc_info=True,
        )
        # Throwing exception further because if the grant failed to apply, we don't want to do anything else
        raise e

    # Convert all mentions to nicknames
    recipient_nicknames = []
    for mention in mentions:
        recipient_nicknames.append(await get_nickname_by_id_or_mention(mention))
    # Add transaction to history
    await db.add_free_transactions_history_item(
        FreeFundingTransaction(
            author_id=ctx.message.author.id,
            author_nickname=await get_nickname_by_id_or_mention(author_mention),
            recipient_ids=DB_ARRAY_COLUMN_SEPARATOR.join(ids),
            recipient_nicknames=DB_ARRAY_COLUMN_SEPARATOR.join(recipient_nicknames),
            total_amount=amount * len(mentions),
            description=description,
            submitted_at=datetime.now(),
            message_url=grant_message.jump_url,
        )
    )
    await ctx.message.add_reaction(REACTION_ON_TRANSACTION_SUCCEED)

    logger.info(
        "Successfully sent free funding. author=%s, remaining balance=%d, total_sum=%d, mentions=%s, message_id=%d",
        author_mention,
        author_balance.balance,
        amount * len(mentions),
        mentions,
        original_message.id,
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
            await ctx.message.add_reaction(REACTION_ON_TRANSACTION_FAILED)
            logger.info(
                "Rejecting the transaction from %s because a stopcock file is detected.",
                ctx.message.author.mention,
            )
            return

        # Don't accept transactions if recovery is in progress
        if db.is_recovery():
            await original_message.reply(FREE_FUNDING_PAUSED_RECOVERY_RESPONSE)
            await ctx.message.add_reaction(REACTION_ON_TRANSACTION_FAILED)
            logger.info(
                "Rejecting the transaction from %s because recovery is in progress.",
                ctx.message.author.mention,
            )
            return

        # Validate that the user is allowed to use the command
        if not await validate_roles(ctx.message.author):
            await original_message.reply(ERROR_MESSAGE_INVALID_ROLE)
            await ctx.message.add_reaction(REACTION_ON_TRANSACTION_FAILED)
            logger.info("Unauthorized user. message_id=%d", original_message.id)
            return

        # If the command is used without arguments, return the user balance
        if len(args) == 0:
            await send_free_funding_balance(ctx)
            return

        # Check for "simplified" format - if the message is a reply, and there's no mention, send funds to the author of the referenced message
        if ctx.message.reference is not None:
            # Check if the command doesn't have a mention - only amount, and optionally - description (as there's clearly a reference)
            # The regex captures a command format that starts with DISCORD_COMMAND_PREFIX, followed by a word (command name) - "^{DISCORD_COMMAND_PREFIX}\w+\s+", followed by a numerical value (amount, may include dots as floating separators) - ([\d\.]+), and ends with any remaining characters (description) - ([\w\W]+)
            match = re.search(
                rf"^{DISCORD_COMMAND_PREFIX}\w+\s+([\d\.]+)\s*([\w\W]*)$",
                message_content,
            )
            if match:
                # Extract the parameters
                amount = float(match.group(1))
                description = match.group(2)

                # Retrieve the author of the original message
                reply_message = await ctx.fetch_message(ctx.message.reference.message_id)
                mentions = [reply_message.author.mention]
                ids = [get_id_by_mention(mentions[0])]

                # Send the transaction
                await send_transaction(ctx, original_message, mentions, ids, amount, description)
                return

        # Check the command matches a default format: mentions amount description
        # Description is obligatory as opposed to the "simplified" format above, because when there's no reference or description, how can one find out why the funds are sent?
        # The regex captures a command format that starts with DISCORD_COMMAND_PREFIX, followed by a word (command name) - "^{DISCORD_COMMAND_PREFIX}\w+\s+", followed by one or more <@userid> mentions separated by whitespace - ((?:<@\d+>\s+)+), followed by a numerical value (amount, may include dots as floating separators) - ([\d\.]+), and ends with any remaining characters (description) - ([\w\W]+)
        match = re.search(
            rf"^{DISCORD_COMMAND_PREFIX}\w+\s+((?:<@\d+>\s+)+)([\d\.]+)\s+([\w\W]+)$",
            message_content,
        )
        if not match:
            # If the format doesn't match, reply that it's wrong
            await original_message.reply(ERROR_MESSAGE_FREE_FUNDING_INVALID_COMMAND_FORMAT)
            await ctx.message.add_reaction(REACTION_ON_TRANSACTION_FAILED)
            logger.info(
                "Invalid command format. message_id=%d, invalid value=%s",
                original_message.id,
                original_message.content,
            )
            return

        # Extract the parameters
        mentions = match.group(1).split()
        ids = [get_id_by_mention(mention) for mention in mentions]
        amount = float(match.group(2))
        description = match.group(3)

        # Send the transaction
        await send_transaction(ctx, original_message, mentions, ids, amount, description)

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
