import sys
import traceback
import logging

from bot.utils.db_utils import DBUtil
from bot.config.logging_config import log_handler, console_handler, DEFAULT_LOG_LEVEL
from bot.utils.proposal_utils import add_proposal, get_proposals_count
from bot.utils.discord_utils import get_discord_client, get_message
from bot.utils.validation import validate_roles
from bot.config.const import CANCEL_EMOJI_UNICODE, VOTING_CHANNEL_ID

# imports below are needed to make discord client aware of decorated methods
from bot.propose import approve_proposal, propose_command
from bot.vote import on_raw_reaction_add
from bot.help import help

logger = logging.getLogger(__name__)
logger.setLevel(DEFAULT_LOG_LEVEL)
logger.addHandler(log_handler)
logger.addHandler(console_handler)


async def sync_voters_db_with_discord(client, proposal):
    """
    Updates voters in the database based on the reactions on the voting message associated with the given proposal.
    Voters who have added cancel reaction but are not in the database are added to the database.
    Voters who are in the database but have not added cancel reaction are removed from the database.

    :param proposal: The proposal for which to update voters.
    """
    # Retrieve the voting message
    client = get_discord_client()
    voting_message = await get_message(client, VOTING_CHANNEL_ID, proposal.voting_message_id)

    # Retrieve all users who added cancel reaction to the message
    x_reactions = [
        reaction
        for reaction in voting_message.reactions
        if str(reaction.emoji) == CANCEL_EMOJI_UNICODE
    ]
    x_reactors = []
    for x_reaction in x_reactions:
        # Retrieve all users who added the cancel reaction
        async for user in x_reaction.users():
            # Check if the user is a valid member to participate in voting
            if not await validate_roles(user):
                return False
            x_reactors.append(user)

    # Process each user who added the cancel reaction
    for reactor in x_reactors:
        # Retrieve the user from DB
        voter = await get_voter(reactor.user_id, proposal.voting_message_id)

        if not voter:
            # If voter is not in DB, add it
            logger.info(
                f"Adding voter {reactor.user_id} to DB for proposal {proposal.voting_message_id}"
            )
            await add_voter(
                proposal,
                Voters(user_id=reactor.user_id, voting_message_id=proposal.voting_message_id),
            )

    # Remove voters whose cancel reaction is not found on the message
    for voter in proposal.voters:
        voter_reacted = False
        for x_reaction in x_reactions:
            async for user in x_reaction.users():
                if user.user_id == voter.user_id:
                    voter_reacted = True
                    break
            if voter_reacted:
                break

        if not voter_reacted:
            logger.info(f"Removing voter {voter.user_id} from DB for proposal {proposal.id}")
            await remove_voter(proposal, voter)


async def start_proposals_coroutines(client, pending_grant_proposals):
    """
    Restores and actualises all active proposals stored in DB. Should run after the client will be initialised.
    """
    logger.info("Running approval of the proposals...")

    # Start background tasks to approve pending proposals
    for proposal in pending_grant_proposals:
        # Update voters that were added or removed during the downtime
        await sync_voters_db_with_discord(client, proposal)
        # Add approval coroutine to event loop
        client.loop.create_task(approve_proposal(proposal.voting_message_id))
        logger.info(
            "Added task to event loop to approve voting_message_id=%d",
            proposal.voting_message_id,
        )
        logger.debug("Loaded a proposal: %s", proposal)


def main():

    try:
        db = DBUtil()
        # Initialise the database, only needed to call once
        # Later the ORM session object will be shared across coroutines using asyncronous awaits
        db.connect_db()
        # Create required tables that don't exist
        db.create_all_tables()
        # Create bot client
        client = get_discord_client()

        # Load pending proposals from database
        pending_grant_proposals = db.load_pending_grant_proposals()
        for proposal in pending_grant_proposals:
            # Adding proposal without db parameter to only keep it in primary memory (as it's already in db)
            # Voters will also be restored (thanks to a bidirectional relationship with voters)
            add_proposal(proposal)
        logger.info("Loaded %d pending grant proposal(s) from database", get_proposals_count())

        # Enabling setup hook to start proposal approving coroutines after the client will be initialised.
        # client.run call is required before approve_grant_proposal, because it starts Discord event loop.
        client.setup_hook = lambda: start_proposals_coroutines(client, pending_grant_proposals)

        # Read token from the file and start the bot
        with open("token", "r") as f:
            token = f.read().strip()
        logger.info("Starting the bot...")
        client.run(token)

    except Exception as e:
        logger.error("An error occurred in main(): %s", e)
        raise
    finally:
        db.close_db()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error("Script crashed: %s", e, exc_info=True)
        traceback.print_exc()
        sys.exit(1)
