import logging

import discord
from discord import client

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
from schemas.grant_proposals import Voters

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(log_handler)
logger.addHandler(console_handler)

db = DBUtil()
client = get_discord_client()


async def is_valid_voting_reaction(payload):
    # Check if the reaction matches
    if payload.emoji.name != CANCEL_EMOJI_UNICODE:
        return False

    # Check if the user role matches
    guild = client.get_guild(payload.guild_id)
    member = guild.get_member(payload.user_id)
    if not await validate_roles(member):
        return False

    # Check if the channel matches
    reaction_channel = guild.get_channel(payload.channel_id)
    if reaction_channel.id != VOTING_CHANNEL_ID:
        reaction_message_id = payload.message_id
        # TODO feature: check if reaction was made to a wrong message - either to bot reply or original proposer message, remove the reaction, and send user private message in channel explaining where he should add reaction
        return False

    # Check if the reaction message is a relevant lazy consensus voting
    if not is_relevant_grant_proposal(reaction_message_id):
        return False
    return True


@client.event
async def on_message(message):
    """
    React with greetings emoji to any message where bot is mentioned.
    """
    if client.user in message.mentions:
        await message.add_reaction(REACTION_ON_BOT_MENTION)


@client.event
async def on_raw_reaction_remove(payload):
    try:
        # Check if the reaction was made by valid user to a valid voting message
        if not is_valid_voting_reaction(payload):
            return

        proposal = get_grant_proposal(reaction_message_id)

        # Error handling - retrieve the voter object from the DB
        voter = Voters.query.filter(
            Voters.user_id == payload.user_id, Voters.voting_message_id == payload.message_id
        ).first()
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
        grant_proposal = GrantProposals.query.filter_by(
            voting_message_id=payload.message_id
        ).first()
        grant_proposal.voters.remove(voter)
        # Remove voter from Voters table; this method calls session.commit(), so the previous line changes will be saved as well
        db.delete(voter)

    except Exception as e:
        try:
            channel = client.get_channel(payload.channel_id)
            message = await channel.fetch_message(payload.message_id)
            await message.reply(
                "An unexpected error occurred when handling reaction removal. cc "
                + RESPONSIBLE_MENTION
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
        traceback.print_exc()


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
        list_of_voters = proposal = proposal.voters
        original_message = await get_message(client, proposal.channel_id, proposal.message_id)
        link_to_voting_message = voting_message.jump_url
        link_to_initial_proposer_message = original_message.jump_url

        # Filling the messages
        if reason == ProposalResult.CANCELLED_BY_PROPOSER:
            response_to_proposer = PROPOSAL_RESULT_PROPOSER_RESPONSE[reason].format(
                author=mention_author
            )
            edit_in_voting_channel = PROPOSAL_RESULT_VOTING_CHANNEL[reason].format()
            log_message = "(by the proposer)"
        elif reason == ProposalResult.CANCELLED_BY_REACHING_THRESHOLD:
            response_to_proposer = PROPOSAL_RESULT_PROPOSER_RESPONSE[reason].format(
                author=mention_author,
                threshold=LAZY_CONSENSUS_THRESHOLD,
                voting_link=link_to_voting_message,
            )
            edit_in_voting_channel = PROPOSAL_RESULT_VOTING_CHANNEL[reason].format(
                threshold=LAZY_CONSENSUS_THRESHOLD, list_of_voters=list_of_voters
            )
            log_message = "(by reaching threshold)"

        # Reply in the original channel
        await original_message.channel.send(response_to_proposer)
        # Edit the proposal in the voting channel
        reaction_message = await reaction_channel_id.fetch_message(reaction_message_id)
        await reaction_message.edit(
            content=PROPOSAL_RESULT_VOTING_CHANNEL_EDITED_MESSAGE.format(
                result=edit_in_voting_channel
            )
        )
        # Remove the proposal
        remove_grant_proposal(proposal.id)
        logger.info("Cancelled grant proposal %s. id=%d", log_message, proposal.id)

    try:
        if not is_valid_voting_reaction(payload):
            return

        proposal = get_grant_proposal(reaction_message_id)

        # The voting message is needed to format the replies of the bot later
        reaction_channel = guild.get_channel(payload.channel_id)
        voting_message = await reaction_channel.get_message(payload.message_id)
        #  Check whether the voter is the proposer himself, and then cancel the proposal
        if proposal.author_id == payload.user_id:
            await cancel_proposal(proposal, ProposalResult.CANCELLED_BY_PROPOSER, voting_message)
            return

        # Error/fraud handling - check if the user has already voted for this proposal
        voter = Voters.query.filter(
            Voters.user_id == payload.user_id, Voters.voting_message_id == payload.message_id
        ).first()
        if voter:
            logger.warning(
                "Warning: Somehow the user has managed to vote twice on the same proposal. channel=%s, message=%s, user=%s, proposal=%s",
                payload.channel_id,
                payload.message_id,
                payload.user_id,
                proposal,
            )
            return

        # Check if the threshold is reached
        if len(proposal.voters) < LAZY_CONSENSUS_THRESHOLD:
            proposal.voters.append(
                Voters(user_id=payload.user_id, voting_message_id=proposal.voting_message_id)
            )
            db.session.commit()
        else:
            await cancel_proposal(
                proposal, ProposalResult.CANCELLED_BY_REACHING_THRESHOLD, voting_message
            )

    except Exception as e:
        try:
            channel = client.get_channel(payload.channel_id)
            message = await channel.fetch_message(payload.message_id)
            await message.reply(
                "An unexpected error occurred when handling reaction adding. cc "
                + RESPONSIBLE_MENTION
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
        traceback.print_exc()
