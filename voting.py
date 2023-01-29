import logging

import discord

from utils.grant_utils import (
    get_grant_proposal,
    add_grant_proposal,
    remove_grant_proposal,
    is_relevant_grant_proposal,
)
from utils.db_utils import DBUtil
from utils import db_utils
from utils.logging_config import log_handler, console_handler
from utils.validation import validate_roles
from utils.bot_utils import get_discord_client
from utils.server_utils import get_message
from utils.const import *
from schemas.grant_proposals import Voters, GrantProposals

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(log_handler)
logger.addHandler(console_handler)

db = DBUtil()
client = get_discord_client()


async def is_valid_voting_reaction(payload):
    logger.debug("Verifying the reaction...")

    # Check if the reaction matches
    if payload.emoji.name != CANCEL_EMOJI_UNICODE:
        return False
    logger.debug("Emoji is correct")

    # Check if the user role matches
    guild = client.get_guild(payload.guild_id)
    member = guild.get_member(payload.user_id)
    if not await validate_roles(member):
        return False
    logger.debug("Role is correct")

    # Check if this is a voting channel
    # TODO this check occurs on every reaction added to server, and it is really consuming so it's worth disabling after a short period of time when most users will be onboarded
    reaction_channel = guild.get_channel(payload.channel_id)
    if reaction_channel.id != VOTING_CHANNEL_ID:
        # Check if the user has attempted to vote on a wrong message - either the original proposer message, or the bots reply to it
        incorrect_reaction_message = await db.filter(
            GrantProposals,
            GrantProposals.message_id == payload.message_id
            or GrantProposals.bot_response_message_id == payload.message_id,
        )
        if incorrect_reaction_message:
            # Remove reaction from the message, in order not to confuse other members
            await reaction_channel.fetch_message(payload.message_id).remove_reaction(
                payload.emoji, member
            )
            # Retrieve the relevant voting message to send link to the user
            voting_message = await get_message(
                client, VOTING_CHANNEL_ID, incorrect_reaction_message.voting_message_id
            )
            # send private message to user
            dm_channel = await member.create_dm()
            await dm_channel.send(
                f'Please add reactions to the voting message in {VOTING_CHANNEL_ID}'
            )
        return False
    logger.debug("Channel is correct")

    # Check if the reaction message is a relevant lazy consensus voting
    if not is_relevant_grant_proposal(payload.message_id):
        return False
    logger.debug("Proposal is correct")
    return True


@client.event
async def on_raw_reaction_remove(payload):
    try:
        # Check if the reaction was made by valid user to a valid voting message
        if not await is_valid_voting_reaction(payload):
            return

        # Get the proposal (it was already validated that it exists)
        proposal = get_grant_proposal(payload.message_id)

        # Error handling - retrieve the voter object from the DB
        voter = await db.filter(
            Voters.user_id == payload.user_id, Voters.voting_message_id == payload.message_id
        )
        if not voter:
            logger.warning(
                "Warning: Unable to find in the DB a user whose voting reaction was presented on active proposal. channel=%s, message=%s, user=%s, proposal=%s",
                payload.channel_id,
                payload.message_id,
                payload.user_id,
                proposal,
            )
            return

        # Remove the voter from the list of voters for the grant proposal
        proposal.voters.remove(voter)
        # Remove the voter from Voters table; this method invokes session.commit(), so the previous line changes will be saved as well
        db.delete(voter)

    except Exception as e:
        try:
            # Try replying in Discord
            message = await get_message(client, payload.channel_id, payload.message_id)
            await message.reply(
                f"An unexpected error occurred when handling reaction removal. cc {RESPONSIBLE_MENTION}"
            )
        except Exception as e:
            logger.critical("Unable to reply in the chat that a critical error has occurred.")

        logger.critical(
            "Unexpected error in %s while removing vote (reaction), channel=%s, message=%s, user=%s",
            __name__,
            payload.channel_id,
            payload.message_id,
            payload.user_id,
            exc_info=True,
        )


@client.event
async def on_raw_reaction_add(payload):
    """
    Cancel a grant proposal if a L3 member reacts with a :x: emoji to the original message or the confirmation message.
    Parameters:
        payload (discord.RawReactionActionEvent): The event containing data about the reaction.
    """

    async def cancel_proposal(proposal, reason, voting_message):
        # Extracting dynamic data to fill messages
        # Don't remove unused variables because messages text may change
        mention_author = proposal.author
        mention_receiver = proposal.mention
        amount_of_allocation = proposal.amount
        description_of_proposal = proposal.description
        list_of_voters = ",".join(f"<@{voter.user_id}>" for voter in proposal.voters)
        original_message = await get_message(client, proposal.channel_id, proposal.message_id)
        link_to_voting_message = voting_message.jump_url
        link_to_initial_proposer_message = original_message.jump_url

        # Filling the messages
        if reason == ProposalResult.CANCELLED_BY_PROPOSER:
            response_to_proposer = PROPOSAL_RESULT_PROPOSER_RESPONSE[reason].format(
                author=mention_author
            )
            result_message = PROPOSAL_RESULT_VOTING_CHANNEL[reason].format()
            log_message = "(by the proposer)"
        elif reason == ProposalResult.CANCELLED_BY_REACHING_THRESHOLD:
            response_to_proposer = PROPOSAL_RESULT_PROPOSER_RESPONSE[reason].format(
                author=mention_author,
                threshold=LAZY_CONSENSUS_THRESHOLD,
                voting_link=link_to_voting_message,
            )
            result_message = PROPOSAL_RESULT_VOTING_CHANNEL[reason].format(
                threshold=LAZY_CONSENSUS_THRESHOLD, voters_list=list_of_voters
            )
            log_message = "(by reaching threshold)"
        edit_in_voting_channel = PROPOSAL_RESULT_VOTING_CHANNEL_EDITED_MESSAGE.format(
            result=result_message,
            amount=amount_of_allocation,
            mention=mention_receiver,
            author=mention_author,
            description=description_of_proposal,
            link_to_original_message=link_to_initial_proposer_message,
        )

        # Reply in the original channel, unless it's not the voting channel itself (then not replying to avoid unnecessary spam)
        if voting_message.channel.id != original_message.channel.id:
            await original_message.reply(response_to_proposer)
        # Edit the proposal in the voting channel
        await voting_message.edit(content=edit_in_voting_channel)
        # Remove the proposal
        await remove_grant_proposal(proposal.voting_message_id, db)
        logger.info(
            "Cancelled grant proposal %s. voting_message_id=%d",
            log_message,
            proposal.voting_message_id,
        )

    try:
        if not await is_valid_voting_reaction(payload):
            return

        proposal = get_grant_proposal(payload.message_id)

        # The voting message is needed to format the replies of the bot later
        voting_message = await get_message(client, payload.channel_id, payload.message_id)

        #  Check whether the voter is the proposer himself, and then cancel the proposal
        if proposal.author == payload.member.mention:
            await cancel_proposal(proposal, ProposalResult.CANCELLED_BY_PROPOSER, voting_message)
            return
        logger.debug("Author is not the same")

        # Error/fraud handling - check if the user has already voted for this proposal
        voter = await db.filter(
            Voters.user_id == payload.user_id, Voters.voting_message_id == payload.message_id
        )
        if voter:
            logger.warning(
                "Warning: Somehow the user has managed to vote twice on the same proposal. channel=%s, message=%s, user=%s, proposal=%s",
                payload.channel_id,
                payload.message_id,
                payload.user_id,
                proposal,
            )
            return
        logger.debug("User hasn't voted before")

        # Check if the threshold is reached
        # FIXME use lock to add to db to avoid concurrency errors
        proposal.voters.append(
            Voters(user_id=payload.user_id, voting_message_id=proposal.voting_message_id)
        )
        db.append(
            proposal.voters,
            Voters(user_id=payload.user_id, voting_message_id=proposal.voting_message_id),
        )
        logger.info(
            "Vote added, total %d voters against %d",
            len(proposal.voters),
            proposal.voting_message_id,
        )
        if len(proposal.voters) >= LAZY_CONSENSUS_THRESHOLD:
            logger.debug("Threshold is reached, cancelling")
            await cancel_proposal(
                proposal, ProposalResult.CANCELLED_BY_REACHING_THRESHOLD, voting_message
            )

    except Exception as e:
        try:
            # Try replying in Discord
            message = await get_message(client, payload.channel_id, payload.message_id)

            await message.reply(
                f"An unexpected error occurred when handling reaction adding. cc {RESPONSIBLE_MENTION}"
            )
        except Exception as e:
            logger.critical("Unable to reply in the chat that a critical error has occurred.")

        logger.critical(
            "Unexpected error in %s while voting (adding reaction), channel=%s, message=%s, user=%s",
            __name__,
            payload.channel_id,
            payload.message_id,
            payload.user_id,
            exc_info=True,
        )
