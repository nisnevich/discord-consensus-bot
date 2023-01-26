import discord
from typing import Union
from typing import Optional

from schemas.grant_proposals import GrantProposals
from utils.db_utils import DBUtil

grant_proposals = {}


def get_grant_proposal(message_id):
    if message_id in grant_proposals:
        return grant_proposals[message_id]
    else:
        logger.critical(
            f"Unable to get the proposal {message_id} - it couldn't be found in the list of active proposals."
        )
        raise ValueError(f"Invalid proposal ID: {message_id}")


def is_relevant_grant_proposal(message_id):
    return message_id in grant_proposals


def get_grant_proposals_count():
    return len(grant_proposals)


async def remove_grant_proposal(message_id, db: DBUtil):
    if message_id in grant_proposals:
        del grant_proposals[message_id]
        # Removing from DB
        await db.delete(proposal)
        logger.info("Removed data: %s", proposal)
    else:
        logger.critical(
            f"Unable to remove the proposal {message_id} - it couldn't be found in the list of active proposals."
        )
        raise ValueError(f"Invalid proposal ID: {message_id}")


async def add_grant_proposal(new_grant_proposal: GrantProposals, db: DBUtil):
    if not isinstance(new_grant_proposal.message_id, int):
        raise ValueError(
            f"message_id should be an int, got {type(new_grant_proposal.message_id)} instead: {new_grant_proposal.message_id}"
        )
    if not isinstance(new_grant_proposal.channel_id, int):
        raise ValueError(
            f"channel_id should be an int, got {type(new_grant_proposal.channel_id)} instead: {new_grant_proposal.channel_id}"
        )
    if not isinstance(new_grant_proposal.author, (discord.User, str)):
        raise ValueError(
            f"author should be discord.User or str, got {type(new_grant_proposal.author)} instead: {new_grant_proposal.author}"
        )
    if not isinstance(new_grant_proposal.voting_message_id, int):
        raise ValueError(
            f"voting_message_id should be an int, got {type(new_grant_proposal.voting_message_id)} instead: {new_grant_proposal.voting_message_id}"
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

    grant_proposals[new_grant_proposal.voting_message_id] = new_grant_proposal
    # Saving to DB
    await db.add(new_grant_proposal)
    logger.info("Inserted data: %s", new_grant_proposal)
