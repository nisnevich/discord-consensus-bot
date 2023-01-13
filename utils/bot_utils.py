import discord
from discord.ext import commands
from typing import Optional

client = None


def get_discord_client(prefix: Optional[str] = "!") -> commands.Bot:
    """
    Initialize and return an instance of Discord bot client with the permissions that are needed for
    the application.
    """
    global client

    if client is None:
        intents = discord.Intents.default()
        intents.members = True
        intents.messages = True
        intents.emojis = True
        client = commands.Bot(prefix, intents=intents)

    # Add validation for the client
    if not isinstance(client, commands.Bot):
        raise ValueError("Client should be an instance of discord.ext.commands.Bot")
    if not client.command_prefix:
        raise ValueError("Client should have a command prefix set")

    return client
