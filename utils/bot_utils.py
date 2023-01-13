import discord
from discord.ext import commands

client = None


def get_discord_client(prefix: Optional[str] = "!") -> commands.Bot:
    """
    Initialize and return an instance of Discord bot client.
    """
    if client is None:
        client = commands.Bot(prefix)

    # Add validation for the client
    if not isinstance(client, commands.Bot):
        raise ValueError("Client should be an instance of discord.ext.commands.Bot")
    if not client.command_prefix:
        raise ValueError("Client should have a command prefix set")

    return client
