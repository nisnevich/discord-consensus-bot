from datetime import datetime, timedelta


def get_discord_timestamp_plus_delta(delta_seconds: int, timestamp_string="<t:{timestamp}>"):
    # TODO add docs and validation
    # Get the current date and time in UTC
    now = datetime.now()
    # Add 3 days to the current date and time
    three_days_later = now + timedelta(seconds=delta_seconds)
    # Convert the datetime object to a timestamp
    timestamp = int(three_days_later.timestamp())

    return timestamp_string.format(timestamp=timestamp)


def get_discord_countdown_plus_delta(delta_seconds: int):
    timestamp_countdown = "<t:{timestamp}:R>"
    return get_discord_timestamp_plus_delta(delta_seconds, timestamp_string=timestamp_countdown)
