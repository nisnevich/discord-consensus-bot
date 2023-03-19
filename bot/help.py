import logging
import csv
import io
import discord
import openpyxl
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo

from bot.config.const import *
from bot.config.logging_config import log_handler, console_handler
from bot.utils.discord_utils import get_discord_client, get_message, get_user_by_id_or_mention
from bot.utils.validation import validate_roles
from bot.utils.db_utils import DBUtil
from bot.utils.formatting_utils import get_amount_to_print, get_nickname_by_id_or_mention
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

    # Replace curly quotes with standard quotes - otherwise it causes errors when used like !gift @Consensus-Dev#0594 500 don’t worry, be happy :blush:
    message.content = message.content.replace('’', "'")
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
        # Add author to DB if not added yet
        if not author_balance:
            logger.debug("Added free funding balance for author=%s", author_mention)
            author_balance = FreeFundingBalance(
                author=author_mention,
                nickname=await get_nickname_by_id_or_mention(author_mention),
                balance=FREE_FUNDING_LIMIT_PERSON_PER_SEASON,
            )
            await db.add(author_balance)

        # Reply with the balance
        await ctx.message.add_reaction(REACTION_ON_BOT_MENTION)
        await ctx.message.reply(
            FREE_FUNDING_BALANCE_MESSAGE.format(balance=get_amount_to_print(author_balance.balance))
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


def define_columns(page, columns):
    """
    Columns are defined the same way for each page, with bold headers.
    """
    # Write the column names to the worksheet and set column widths
    for col_num, column in enumerate(columns, 1):
        column_letter = get_column_letter(col_num)
        column_header = column["header"]
        column_width = column["width"]
        page.column_dimensions[column_letter].width = column_width
        page.cell(row=1, column=col_num, value=column_header).font = Font(bold=True)


async def write_lazy_consensus_history(page):
    # Define column names and widths
    columns = [
        {"header": "Discord link", "width": 15},
        {"header": "When completed (UTC time)", "width": 28},
        {"header": "Author", "width": 15},
        {"header": "Grant given to", "width": 15},
        {"header": "Amount", "width": 10},
        {"header": "Description", "width": 100},
    ]
    # Enable the columns in the page
    define_columns(page, columns)

    # Retrieve all accepted proposals
    accepted_proposals = await db.filter(
        ProposalHistory,
        condition=(ProposalHistory.result == ProposalResult.ACCEPTED.value),
        order_by=ProposalHistory.closed_at.asc(),
    )
    # Loop over each accepted proposal and add a row to the worksheet
    for row_num, proposal in enumerate(accepted_proposals.all(), 2):
        # Discord URL
        discord_link = proposal.voting_message_url
        page.cell(row=row_num, column=1).value = discord_link
        page.cell(row=row_num, column=1).hyperlink = discord_link
        # Date
        page.cell(row=row_num, column=2, value=proposal.closed_at.strftime("%Y-%m-%d %H:%M:%S"))
        # Author
        page.cell(row=row_num, column=3, value=str(proposal.author_id))
        # Mention
        page.cell(
            row=row_num,
            column=4,
            value=str(proposal.receiver_ids)
            if proposal.receiver_ids is not None
            else EMPTY_ANALYTICS_VALUE,
        )
        # Amount
        page.cell(
            row=row_num,
            column=5,
            value=str(get_amount_to_print(proposal.amount))
            if proposal.amount is not None
            else EMPTY_ANALYTICS_VALUE,
        )
        # Description
        page.cell(row=row_num, column=6, value=str(proposal.description))


async def write_free_funding_balance(page):
    # Define column names and widths
    columns = [
        {"header": "Author", "width": 15},
        {"header": "Remaining balance", "width": 20},
    ]
    # Enable the columns in the page
    define_columns(page, columns)
    # Write a note in the corner
    page.cell(
        row=1, column=3, value="Note: only users that have used tips in this season are listed here"
    ).font = Font(italic=True)

    # Retrieve all balances
    all_balances = await db.filter(FreeFundingBalance, is_history=False)

    # Loop over each users balance and add a row to the worksheet
    for row_num, balance in enumerate(all_balances.all(), 2):
        # Author
        page.cell(row=row_num, column=1, value=str(balance.nickname))
        # Amount
        page.cell(row=row_num, column=2, value=str(get_amount_to_print(balance.balance)))


async def write_free_funding_transactions(page):
    # Define column names and widths
    columns = [
        {"header": "Discord link", "width": 15},
        {"header": "UTC time", "width": 20},
        {"header": "Author", "width": 15},
        {"header": "Sent to", "width": 20},
        {"header": "Total amount", "width": 15},
        {"header": "Description", "width": 100},
    ]
    # Enable the columns in the page
    define_columns(page, columns)

    # Retrieve all transactions
    all_transactions = await db.filter(
        FreeFundingTransaction,
        order_by=FreeFundingTransaction.submitted_at.asc(),
    )

    # Loop over each transaction and add a row to the worksheet
    for row_num, transaction in enumerate(all_transactions.all(), 2):
        # Discord URL
        discord_link = transaction.message_url
        page.cell(row=row_num, column=1).value = discord_link
        page.cell(row=row_num, column=1).hyperlink = discord_link
        # Date
        page.cell(
            row=row_num, column=2, value=transaction.submitted_at.strftime("%Y-%m-%d %H:%M:%S")
        )
        # Author
        page.cell(row=row_num, column=3, value=str(transaction.author))
        # Mentions
        page.cell(row=row_num, column=4, value=str(transaction.mentions))
        # Total amount
        page.cell(row=row_num, column=5, value=str(get_amount_to_print(transaction.total_amount)))
        # Description
        page.cell(row=row_num, column=6, value=str(transaction.description))


async def export_xlsx():
    # Create a new Excel workbook and worksheet
    wb = openpyxl.Workbook()

    # Create a page with a history of all lazy consensus proposals
    lazy_history_page = wb.active
    lazy_history_page.title = "Lazy Consensus History"
    await write_lazy_consensus_history(lazy_history_page)

    # Create a page with free funding balances of all members
    free_funding_balance_page = wb.create_sheet(title="Tips Balances")
    await write_free_funding_balance(free_funding_balance_page)

    # Create a page with all free funding transactions
    free_funding_history_page = wb.create_sheet(title="Tips Transactions")
    await write_free_funding_transactions(free_funding_history_page)

    # Save the Excel workbook to a temporary file
    temp_file = io.BytesIO()
    wb.save(temp_file)
    temp_file.seek(0)

    return temp_file, EXPORT_DATA_FILENAME


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
        # Adding greetings reaction so to show that the command is being processed (it may take a couple of seconds waiting for the user)
        await ctx.message.add_reaction(REACTION_ON_BOT_MENTION)

        # Create the document
        document, filename = await export_xlsx()
        # Send the document to user
        await ctx.message.reply(
            EXPORT_CHANNEL_REPLY,
            file=discord.File(document, filename=filename),
        )

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
