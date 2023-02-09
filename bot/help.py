import logging

from bot.config.const import (
    HELP_MESSAGE_NON_AUTHORIZED_USER,
    HELP_MESSAGE_AUTHORIZED_USER,
    RESPONSIBLE_MENTION,
    HELP_COMMAND_NAME,
    DEFAULT_LOG_LEVEL,
)
from bot.config.logging_config import log_handler, console_handler
from bot.utils.discord_utils import get_discord_client
from bot.utils.validation import validate_roles

logger = logging.getLogger(__name__)
logger.setLevel(DEFAULT_LOG_LEVEL)
logger.addHandler(log_handler)
logger.addHandler(console_handler)

client = get_discord_client()


@client.command(name=HELP_COMMAND_NAME)
async def help(ctx):
    try:
        # Remove the help request message
        await ctx.message.delete()
        # Reply to a non-authorized user
        if not await validate_roles(ctx.message.author):
            await ctx.author.send(HELP_MESSAGE_NON_AUTHORIZED_USER)
            return
        # Reply to an authorized user
        await ctx.author.send(HELP_MESSAGE_AUTHORIZED_USER)
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
            ctx.message.channel.id,
            ctx.message.id,
            ctx.message.author.mention,
            exc_info=True,
        )
