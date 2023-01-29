import discord
from discord.ext import commands
from typing import Optional

from utils.const import DISCORD_COMMAND_PREFIX

client = None


def get_discord_client(
    prefix: Optional[str] = DISCORD_COMMAND_PREFIX, help_command=None
) -> commands.Bot:
    """
    Initialize and return an instance of Discord bot client with the permissions that are needed for the application.
    """
    global client

    if client is None:
        intents = discord.Intents.default()
        # To use Intents.default() instead of .all(), enable priveliged message content manually:
        intents.message_content = True
        intents.members = True

        client = commands.Bot(command_prefix=prefix, intents=intents, help_command=help_command)

    # Add validation for the client
    if not isinstance(client, commands.Bot):
        raise ValueError("Client should be an instance of discord.ext.commands.Bot")
    if not client.command_prefix:
        raise ValueError("Client should have a command prefix set")

    return client
