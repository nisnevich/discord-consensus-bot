from datetime import datetime, timedelta
import re


def get_discord_timestamp_plus_delta(delta_seconds: int, timestamp_string="<t:{timestamp}>"):
    """
    Returns a discord timestamp string in the format "<t:{timestamp}>" that is delta_seconds
    seconds in the future from the current time.
    :param delta_seconds: int - Number of seconds to add to the current time.
    :param timestamp_string: str - The string format for the timestamp. Must include "{timestamp}"
    :return: str - Discord timestamp string in the format "<t:{timestamp}>"
    """
    if not isinstance(delta_seconds, int):
        raise TypeError("delta_seconds must be an int")
    if delta_seconds < 0:
        raise ValueError("delta_seconds must be a positive int")
    if not isinstance(timestamp_string, str):
        raise TypeError("timestamp_string must be a string")
    match = re.search("{timestamp}", timestamp_string)
    if not match:
        raise ValueError("timestamp_string must contain the string '{timestamp}'")

    # Get the current date and time in UTC
    now = datetime.now()
    # Add delta_seconds to the current date and time
    later = now + timedelta(seconds=delta_seconds)
    # Convert the datetime object to a timestamp
    timestamp = int(later.timestamp())

    return timestamp_string.format(timestamp=timestamp)


def get_discord_countdown_plus_delta(delta_seconds: int):
    timestamp_countdown = "<t:{timestamp}:R>"
    return get_discord_timestamp_plus_delta(delta_seconds, timestamp_string=timestamp_countdown)
