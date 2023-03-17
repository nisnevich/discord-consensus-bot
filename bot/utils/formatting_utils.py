import re
import discord

from datetime import datetime, timedelta
from bot.utils.discord_utils import get_user_by_id_or_mention


def get_discord_timestamp_plus_delta(delta_seconds, timestamp_string="<t:{timestamp}>"):
    """
    Returns a discord timestamp string in the format "<t:{timestamp}>" that is delta_seconds
    seconds in the future from the current time.
    :param delta_seconds: int or timedelta - Number of seconds to add to the current time.
    :param timestamp_string: str - The string format for the timestamp. Must include "{timestamp}"
    :return: str - Discord timestamp string in the format "<t:{timestamp}>"
    """
    if not isinstance(delta_seconds, int) and not isinstance(delta_seconds, timedelta):
        raise TypeError("delta_seconds must be an int or timedelta")
    if isinstance(delta_seconds, int) and delta_seconds < 0:
        raise ValueError("delta_seconds must be a positive number")
    if not isinstance(timestamp_string, str):
        raise TypeError("timestamp_string must be a string")
    match = re.search("{timestamp}", timestamp_string)
    if not match:
        raise ValueError("timestamp_string must contain the string '{timestamp}'")

    # Get the current local date and time (Discord will convert the timestamp into the local time of
    # each specific user)
    now = datetime.now()
    # Add delta_seconds to the current date and time
    later = now + (
        delta_seconds if isinstance(delta_seconds, timedelta) else timedelta(seconds=delta_seconds)
    )
    # Convert the datetime object to a timestamp
    timestamp = int(later.timestamp())

    return timestamp_string.format(timestamp=timestamp)


def get_discord_countdown_plus_delta(delta_seconds):
    timestamp_countdown = "<t:{timestamp}:R>"
    return get_discord_timestamp_plus_delta(delta_seconds, timestamp_string=timestamp_countdown)


def get_amount_to_print(amount):
    """
    Returns int if the number doesn't have a fractional part, or float otherwise. This is so not to
    print amounts like 1.0.
    """
    return int(amount) if amount - int(amount) == 0 else float(amount)


async def get_nickname_by_id_or_mention(id_or_mention):
    """
    Returns a discord nickname of a user based on the user ID or mention, or None if it's not found.
    """
    # Retrieve the user
    user = await get_user_by_id_or_mention(id_or_mention)
    # Return the nickname if the user was found
    if type(user) is discord.User:
        return f"{user.name}#{user.discriminator}"
    # Otherwise return None
    return None


def get_mention_by_id(id):
    return f"<@{id}>"


def remove_discord_mentions(text):
    """
    Removes all kinds of mentions (user, role etc) from the given text.
    """
    return re.sub(r'<@.+>', '', text)


def remove_special_symbols(text):
    return re.sub(r'[^\w\s]', '', text)
