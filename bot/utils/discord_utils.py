import discord
from discord.ext import commands
from typing import Optional

from bot.config.const import DISCORD_COMMAND_PREFIX

client = None


async def get_members_count_with_role(client: discord.Client, role_id: int):
    # Get the guild (server) the client is connected to
    guild = client.guilds[0]
    # Get the role with the specified ID
    role = discord.utils.get(guild.roles, id=role_id)
    # Get all members with the role
    members_with_role = [member for member in guild.members if role in member.roles]
    # Return the length of the list of members with the role
    return len(members_with_role)


async def get_message(client: discord.Client, channel_id: int, message_id: int):
    channel = client.get_channel(channel_id)
    return await channel.fetch_message(message_id)


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


async def get_user_by_id_or_mention(id_or_mention):
    """
    Retrieves the nickname of a Discord user by either their user ID or mention.

    :param id_or_mention: The Discord user ID or mention (e.g. <@703574259401883728>)
    :return: The user on the Discord server
    """
    if id_or_mention.startswith("<@") and id_or_mention.endswith(">"):
        user_id = int(id_or_mention[2:-1].strip("!"))
    else:
        user_id = int(id_or_mention)
    user = await client.fetch_user(user_id)
    return user
