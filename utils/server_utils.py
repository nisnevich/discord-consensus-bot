import discord


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
