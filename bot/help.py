import logging
import csv
import io
import discord

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
)
from bot.config.logging_config import log_handler, console_handler
from bot.utils.discord_utils import get_discord_client, get_message, get_user_by_id_or_mention
from bot.utils.validation import validate_roles
from bot.utils.db_utils import DBUtil
from bot.utils.formatting_utils import get_amount_to_print
from bot.config.schemas import ProposalHistory
from bot.config.const import ProposalResult, VOTING_CHANNEL_ID

logger = logging.getLogger(__name__)
logger.setLevel(DEFAULT_LOG_LEVEL)
logger.addHandler(log_handler)
logger.addHandler(console_handler)

client = get_discord_client()


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
            await ctx.author.send(HELP_MESSAGE_NON_AUTHORIZED_USER)
            return

        # Remove the message requesting the analytics
        await ctx.message.delete()

        accepted_proposals = (
            DBUtil.session_history.query(ProposalHistory)
            .filter(ProposalHistory.result == ProposalResult.ACCEPTED.value)
            .all()
        )
        if len(accepted_proposals) == 0:
            await ctx.author.send("No proposals were accepted yet.")
            return

        file = io.StringIO()
        writer = csv.DictWriter(
            file,
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
        writer.writeheader()

        for proposal in accepted_proposals:
            logger.debug("Exporting %s", proposal)
            writer.writerow(
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

        file.seek(0)

        await ctx.author.send(file=discord.File(file, filename="proposal_history.csv"))

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
