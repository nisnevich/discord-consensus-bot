import logging
import csv
import io
import discord
from openpyxl import Workbook

from bot.config.const import (
    HELP_MESSAGE_NON_AUTHORIZED_USER,
    HELP_MESSAGE_AUTHORIZED_USER,
    RESPONSIBLE_MENTION,
    HELP_COMMAND_NAME,
    DEFAULT_LOG_LEVEL,
    EXPORT_COMMAND_NAME,
    REACTION_ON_BOT_MENTION,
    EMPTY_ANALYTICS_VALUE,
    HELP_COMMAND_ALIASES,
    HELP_MESSAGE_REMOVED_FROM_VOTING_CHANNEL,
    VOTING_CHANNEL_ID,
    REMOVE_HUMAN_MESSAGES_FROM_VOTING_CHANNEL,
    FREE_FUNDING_BALANCE_COMMAND_NAME,
    FREE_FUNDING_BALANCE_ALIASES,
    FREE_FUNDING_BALANCE_MESSAGE,
)
from bot.config.logging_config import log_handler, console_handler
from bot.utils.discord_utils import get_discord_client, get_message, get_user_by_id_or_mention
from bot.utils.validation import validate_roles
from bot.utils.db_utils import DBUtil
from bot.utils.formatting_utils import get_amount_to_print
from bot.config.schemas import ProposalHistory, FreeFundingTransaction, FreeFundingBalance
from bot.config.const import ProposalResult, VOTING_CHANNEL_ID

logger = logging.getLogger(__name__)
logger.setLevel(DEFAULT_LOG_LEVEL)
logger.addHandler(log_handler)
logger.addHandler(console_handler)

db = DBUtil()
client = get_discord_client()


@client.event
async def on_message(message):
    # If the author is not bot, and the message is written in the voting channel, remove the message and DM user, explaining why
    # This is to maintain the channel cleaner
    if (
        REMOVE_HUMAN_MESSAGES_FROM_VOTING_CHANNEL
        and message.channel.id == VOTING_CHANNEL_ID
        and not message.author.bot
    ):
        await message.author.send(HELP_MESSAGE_REMOVED_FROM_VOTING_CHANNEL)
        await message.delete()
        return

    # Process commands (the @client.event decorator intercepts all messages)
    await client.process_commands(message)


@client.command(name=FREE_FUNDING_BALANCE_COMMAND_NAME, aliases=FREE_FUNDING_BALANCE_ALIASES)
async def send_free_funding_balance(ctx):
    try:
        # Reply to a non-authorized user
        if not await validate_roles(ctx.message.author):
            # Adding greetings and "cancelled" reactions
            await ctx.message.add_reaction(REACTION_ON_BOT_MENTION)
            # Sending response in DM
            await ctx.author.send(HELP_MESSAGE_NON_AUTHORIZED_USER)
            return

        # Retrieve the authors balance
        author_mention = str(ctx.message.author.mention)
        author_balance = db.get_user_free_funding_balance(author_mention)
        if author_balance:
            # Reply with the balance
            await ctx.message.add_reaction(REACTION_ON_BOT_MENTION)
            await ctx.message.reply(
                FREE_FUNDING_BALANCE_MESSAGE.format(
                    balance=get_amount_to_print(author_balance.balance)
                )
            )
    except Exception as e:
        try:
            # Try replying in Discord
            await ctx.message.reply(
                f"An unexpected error occurred when sending free funding balance. cc {RESPONSIBLE_MENTION}"
            )
        except Exception as e:
            logger.critical("Unable to reply in the chat that a critical error has occurred.")

        logger.critical(
            "Unexpected error in %s while sending help, channel=%s, message=%s, user=%s",
            __name__,
            ctx.message.channel.id if ctx.message.channel else None,
            ctx.message.id,
            ctx.message.author.mention,
            exc_info=True,
        )


@client.command(name=HELP_COMMAND_NAME, aliases=HELP_COMMAND_ALIASES)
async def help(ctx):
    try:
        # Remove the help request message
        await ctx.message.delete()
        # Reply to a non-authorized user
        if not await validate_roles(ctx.message.author):
            await ctx.author.send(HELP_MESSAGE_NON_AUTHORIZED_USER)
            return
        # Reply to an authorized user
        message = await ctx.author.send(HELP_MESSAGE_AUTHORIZED_USER)
        await message.edit(suppress=True)
    except Exception as e:
        try:
            # Try replying in Discord
            await ctx.message.reply(
                f"An unexpected error occurred when sending help. cc {RESPONSIBLE_MENTION}"
            )
        except Exception as e:
            logger.critical("Unable to reply in the chat that a critical error has occurred.")

        logger.critical(
            "Unexpected error in %s while sending help, channel=%s, message=%s, user=%s",
            __name__,
            ctx.message.channel.id if ctx.message.channel else None,
            ctx.message.id,
            ctx.message.author.mention,
            exc_info=True,
        )


@client.command(name=EXPORT_COMMAND_NAME)
async def export(ctx):
    try:
        # Reply to a non-authorized user
        if not await validate_roles(ctx.message.author):
            # Adding greetings and "cancelled" reactions
            await ctx.message.add_reaction(REACTION_ON_BOT_MENTION)
            # Sending response in DM
            await ctx.message.reply(HELP_MESSAGE_NON_AUTHORIZED_USER)
            return

        # Remove the message requesting the analytics
        await ctx.message.delete()

        accepted_proposals = (
            DBUtil.session_history.query(ProposalHistory)
            .filter(ProposalHistory.result == ProposalResult.ACCEPTED.value)
            .all()
        )

        wb = Workbook()
        page1 = wb.active
        page1.title = "Lazy Consensus"

        writer_lazy_proposals = csv.DictWriter(
            page1,
            fieldnames=[
                "Discord link",
                "When completed (UTC time)",
                "Author",
                "Has grant",
                "Given to",
                "Amount",
                "Description",
            ],
        )
        writer_lazy_proposals.writeheader()

        page2 = wb.create_sheet(title="Tips Balances")
        writer_balance = csv.DictWriter(page2, fieldnames=["Author", "Balance"])
        writer_balance.writeheader()

        page3 = wb.create_sheet(title="Tips History")
        writer_free_transactions = csv.DictWriter(
            page3, fieldnames=["Author", "mentions", "amount", "description", "submitted_at"]
        )
        writer_free_transactions.writeheader()

        for proposal in accepted_proposals:
            logger.debug("Exporting %s", proposal)
            writer_lazy_proposals.writerow(
                {
                    "Discord link": f'=HYPERLINK("{proposal.voting_message_url}", "Open in Discord")',
                    "When completed (UTC time)": proposal.closed_at.strftime("%Y-%m-%d %H:%M:%S"),
                    "Author": proposal.author,
                    "Has grant": not proposal.is_grantless,
                    "Given to": proposal.mention
                    if proposal.mention is not None
                    else EMPTY_ANALYTICS_VALUE,
                    "Amount": get_amount_to_print(proposal.amount)
                    if proposal.amount is not None
                    else EMPTY_ANALYTICS_VALUE,
                    "Description": proposal.description,
                }
            )

        # Export all rows from FreeFundingBalance
        for balance in await db.filter(FreeFundingBalance):
            writer_balance.writerow({"Author": balance.author, "Balance": balance.balance})

        # Export all rows from FreeFundingTransaction
        for transaction in await db.filter(FreeFundingTransaction):
            writer_free_transactions.writerow(
                {
                    "Author": transaction.author,
                    "mentions": transaction.mentions,
                    "amount": transaction.amount,
                    "description": transaction.description,
                    "submitted_at": transaction.submitted_at.strftime("%Y-%m-%d %H:%M:%S"),
                }
            )

        # write the workbook to memory
        file = BytesIO()
        wb.save(file)
        file.seek(0)

        await ctx.channel.send(file=discord.File(file, filename="analytics.xlsx"))

    except Exception as e:
        try:
            # Try replying in Discord
            await ctx.message.reply(
                f"An unexpected error occurred when exporting analytical data. cc {RESPONSIBLE_MENTION}"
            )
        except Exception as e:
            logger.critical("Unable to reply in the chat that a critical error has occurred.")

        logger.critical(
            "Unexpected error in %s while exporting analytical data, channel=%s, message=%s, user=%s",
            __name__,
            ctx.message.channel.id if ctx.message.channel else None,
            ctx.message.id,
            ctx.message.author.mention,
            exc_info=True,
        )
