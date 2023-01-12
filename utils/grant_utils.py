import discord
from typing import Union
from typing import Optional

grant_proposals = {}


def get_grant_proposal(message_id):
    if message_id in grant_proposals:
        return grant_proposals[message_id]
    else:
        raise ValueError(f"Invalid message ID: {message_id}")


def get_grant_proposals_count():
    return len(grant_proposals)


def remove_grant_proposal(message_id):
    if message_id in grant_proposals:
        del grant_proposals[message_id]
    else:
        raise ValueError(f"Invalid message ID: {message_id}")


def add_grant_proposal(
    message_id: int,
    channel_id: int,
    mention: Union[discord.User, str],
    amount: int,
    description: str,
    timer: Optional[int] = 0,
):
    if not isinstance(message_id, int):
        raise ValueError("message_id should be an int")
    if not isinstance(channel_id, int):
        raise ValueError("channel_id should be an int")
    if not isinstance(mention, (discord.User, str)):
        raise ValueError("mention should be discord.User or str")
    if not isinstance(amount, int):
        raise ValueError("amount should be an int")
    if not isinstance(description, str):
        raise ValueError("description should be a string")
    if not isinstance(timer, int):
        raise ValueError("timer should be an int")

    grant_proposals[message_id] = {
        "mention": mention,
        "amount": amount,
        "description": description,
        "timer": timer,
        "message_id": message_id,
        "channel_id": channel_id,
    }
