import logging

import discord
import discord.ext.commands as commands
from utils.const import *
from utils.db_utils import DBUtil
from utils.logging_config import log_handler, console_handler
from utils.bot_utils import get_discord_client

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(log_handler)
logger.addHandler(console_handler)

db = DBUtil()
client = get_discord_client()


class CustomHelpCommand(commands.DefaultHelpCommand):
    async def send_command_help(self, command):
        ctx = self.context
        if command.name == 'help':
            await ctx.send(
                """
!propose @nickname 100 for doing useful things
"""
            )
        else:
            # Use the built-in help command behavior for other commands
            await super().send_command_help(command)


@client.event
async def on_message(message):
    """
    React with greetings emoji to any message where bot is mentioned.
    """
    if client.user in message.mentions:
        await message.add_reaction(REACTION_ON_BOT_MENTION)