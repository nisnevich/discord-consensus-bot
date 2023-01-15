import datetime


def get_discord_timestamp_plus_delta(delta_seconds: int):
    # TODO add docs and validation
    # Get the current date and time in UTC
    now = datetime.datetime.now()
    # Add 3 days to the current date and time
    three_days_later = now + datetime.timedelta(seconds=delta_seconds)
    # Convert the datetime object to a timestamp
    timestamp = int(three_days_later.timestamp())
    # Format the timestamp as a string
    timestamp_string = f"<t:{timestamp}>"

    return timestamp_string