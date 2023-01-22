import discord
from typing import Union
from typing import Optional

from schemas.grant_proposals import GrantProposals

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


def add_grant_proposal(new_grant_proposal: GrantProposals):
    if not isinstance(new_grant_proposal.message_id, int):
        raise ValueError(
            f"message_id should be an int, got {type(new_grant_proposal.message_id)} instead: {new_grant_proposal.message_id}"
        )
    if not isinstance(new_grant_proposal.channel_id, int):
        raise ValueError(
            f"channel_id should be an int, got {type(new_grant_proposal.channel_id)} instead: {new_grant_proposal.channel_id}"
        )
    if not isinstance(new_grant_proposal.mention, (discord.User, str)):
        raise ValueError(
            f"mention should be discord.User or str, got {type(new_grant_proposal.mention)} instead: {new_grant_proposal.mention}"
        )
    if not isinstance(new_grant_proposal.amount, int):
        raise ValueError(
            f"amount should be an int, got {type(new_grant_proposal.amount)} instead: {new_grant_proposal.amount}"
        )
    if not isinstance(new_grant_proposal.description, str):
        raise ValueError(
            f"description should be a string, got {type(new_grant_proposal.description)} instead: {new_grant_proposal.description}"
        )
    if not isinstance(new_grant_proposal.timer, int):
        raise ValueError(
            f"timer should be an int, got {type(new_grant_proposal.timer)} instead: {new_grant_proposal.timer}"
        )

    grant_proposals[new_grant_proposal.message_id] = new_grant_proposal
