from bot.config.const import *
from bot.config.logging_config import log_handler, console_handler
from bot.utils.discord_utils import get_discord_client, send_dm
from bot.utils.validation import validate_roles
from bot.utils.db_utils import DBUtil
from bot.utils.formatting_utils import get_amount_to_print, get_nickname_by_id_or_mention
from bot.config.schemas import (
    FreeFundingBalance,
)
from bot.config.const import VOTING_CHANNEL_ID

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
        author_balance = db.get_user_free_funding_balance(ctx.message.author.id)
        # Add author to DB if not added yet
        if not author_balance:
            logger.debug("Added free funding balance for author=%s", ctx.message.author.id)
            author_balance = FreeFundingBalance(
                author_id=ctx.message.author.id,
                author_nickname=await get_nickname_by_id_or_mention(
                    str(ctx.message.author.mention)
                ),
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
            error_message = f"An unexpected error occurred when sending free funding balance. cc {RESPONSIBLE_MENTION}"
            if PING_RESPONSIBLE_IN_CHANNEL:
                await ctx.message.reply(error_message)
            else:
                await send_dm(
                    ctx.guild.id, RESPONSIBLE_ID, f"{error_message} {ctx.message.jump_url}"
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
            error_message = (
                f"An unexpected error occurred when sending help. cc {RESPONSIBLE_MENTION}"
            )
            if PING_RESPONSIBLE_IN_CHANNEL:
                await ctx.message.reply(error_message)
            else:
                await send_dm(
                    ctx.guild.id, RESPONSIBLE_ID, f"{error_message} {ctx.message.jump_url}"
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
