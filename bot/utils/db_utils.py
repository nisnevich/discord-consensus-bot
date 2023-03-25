import atexit
import asyncio
import datetime
import discord
import os
import copy
import re

from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import Query
from sqlalchemy import create_engine

from bot.config.schemas import (
    Base,
    Proposals,
    ProposalHistory,
    FreeFundingBalance,
    Voters,
    FinanceRecipients,
)
from bot.config.logging_config import log_handler, console_handler
from bot.config.const import *
from bot.utils.discord_utils import get_discord_client, get_message
from bot.utils.formatting_utils import get_nickname_by_id_or_mention

logger = logging.getLogger(__name__)
logger.setLevel(DEFAULT_LOG_LEVEL)
logger.addHandler(log_handler)
logger.addHandler(console_handler)

client = get_discord_client()


class DBUtil:
    engine = None
    session = None
    # The lock is used to prevent concurrency errors when updating DB from event loop coroutines
    session_lock = asyncio.Lock()
    # The history DB uses a separate value
    engine_history = None
    session_history = None
    session_lock_history = asyncio.Lock()

    # The lock used during recovery to stop accepting proposals and voting
    recovery_lock = asyncio.Lock()

    def is_recovery(self):
        if DBUtil.recovery_lock.locked():
            return True
        return False

    def connect_db(self):
        if DBUtil.engine is None:
            DBUtil.engine = create_engine(f"sqlite:///{DB_PATH}")
        if DBUtil.session is None:
            DBUtil.session = sessionmaker(bind=DBUtil.engine)()
        # History db
        if DBUtil.engine_history is None:
            DBUtil.engine_history = create_engine(f"sqlite:///{DB_HISTORY_PATH}")
        if DBUtil.session_history is None:
            DBUtil.session_history = sessionmaker(bind=DBUtil.engine_history)()
        # run close_db once the main thread exits
        atexit.register(self.close_db)

    def close_db(self):
        DBUtil.engine.dispose()
        DBUtil.engine_history.dispose()

    def create_all_tables(self):
        # Creating tables that are only used for bot runtime
        if not DBUtil.engine.has_table(PROPOSALS_TABLE_NAME):
            Base.metadata.create_all(DBUtil.engine)
        else:
            logger.info("Table already exist: %s", PROPOSALS_TABLE_NAME)
        if not DBUtil.engine.has_table(VOTERS_TABLE_NAME):
            Base.metadata.create_all(DBUtil.engine)
        else:
            logger.info("Table already exist: %s", VOTERS_TABLE_NAME)
        if not DBUtil.engine.has_table(FREE_FUNDING_BALANCES_TABLE_NAME):
            Base.metadata.create_all(DBUtil.engine)
        else:
            logger.info("Table already exist: %s", FREE_FUNDING_BALANCES_TABLE_NAME)

        # Creating tables that are used for history and analytics
        if not DBUtil.engine_history.has_table(PROPOSALS_TABLE_NAME):
            Base.metadata.create_all(DBUtil.engine_history)
        else:
            logger.info("Table already exist: %s", PROPOSALS_TABLE_NAME)
        if not DBUtil.engine_history.has_table(VOTERS_TABLE_NAME):
            Base.metadata.create_all(DBUtil.engine_history)
        else:
            logger.info("Table already exist: %s", VOTERS_TABLE_NAME)
        if not DBUtil.engine_history.has_table(PROPOSAL_HISTORY_TABLE_NAME):
            Base.metadata.create_all(DBUtil.engine_history)
        else:
            logger.info("Table already exist: %s", PROPOSAL_HISTORY_TABLE_NAME)
        if not DBUtil.engine_history.has_table(FREE_FUNDING_TRANSACTIONS_TABLE_NAME):
            Base.metadata.create_all(DBUtil.engine_history)
        else:
            logger.info("Table already exist: %s", FREE_FUNDING_TRANSACTIONS_TABLE_NAME)

    def get_user_free_funding_balance(self, author_id) -> Query:
        return DBUtil.session.query(FreeFundingBalance).filter_by(author_id=author_id).first()

    def load_pending_grant_proposals(self) -> Query:
        return DBUtil.session.query(Proposals)

    def log_pending_grant_proposals(self) -> Query:
        # Load pending proposals from database
        pending_grant_proposals = self.load_pending_grant_proposals()
        logger.info("Logging pending proposals in DB on request")
        logger.info("Total: %d", pending_grant_proposals.count())
        for proposal in pending_grant_proposals:
            logger.info(proposal)

    async def filter(self, table, is_history=True, condition=None, order_by=None):
        """
        Filters the given ORM objects and returns a query (results should be retrieved using
        statements like .all() or .first()). The DB is chosen depending on is_history parameter.
        """
        if is_history:
            async with DBUtil.session_lock_history:
                query = DBUtil.session_history.query(table)
        else:
            async with DBUtil.session_lock:
                query = DBUtil.session.query(table)
        if condition is not None:
            query = query.filter(condition)
        if order_by is not None:
            query = query.order_by(order_by)
        return query

    async def add(self, orm_object):
        """
        Adds object to a set.
        """
        async with DBUtil.session_lock:
            DBUtil.session.add(orm_object)
            DBUtil.session.commit()

    async def delete(self, orm_object):
        """
        Deletes object from a set.
        """
        async with DBUtil.session_lock:
            DBUtil.session.delete(orm_object)
            DBUtil.session.commit()

    async def append(self, list, orm_object):
        """
        Appends object to a list.
        """
        async with DBUtil.session_lock:
            list.append(orm_object)
            DBUtil.session.commit()

    async def remove(self, list, orm_object):
        """
        Remove object from a list.
        """
        async with DBUtil.session_lock:
            list.remove(orm_object)
            DBUtil.session.commit()

    async def add_free_transactions_history_item(self, transaction):
        async with DBUtil.session_lock_history:
            DBUtil.session_history.add(transaction)
            DBUtil.session_history.commit()

    async def add_proposals_history_item(self, proposal, result):
        """
        Adds a proposal to the ProposalHistory table after it has been processed.

        Parameters:
        proposal (Proposals): The original proposal that needs to be added to the history.
        result (ProposalResult): The result of the proposal. This should be one of the enumerated values in `ProposalResult`.
        """

        def replace_mentions_with_nicknames(description, id_to_nickname_map):
            """
            Replaces all mentions in a proposal description with nicknames, based on the mapping provided in id_to_nickname_map.
            """

            def replace_mention(match):
                user_id = match.group(1)
                return id_to_nickname_map.get(user_id, f"<@{user_id}>")

            return re.sub(r"<@(\d+)>", replace_mention, description)

        try:
            async with DBUtil.session_lock_history:
                # Copy all attributes from Proposals table (excluding some of them)
                proposal_dict = {
                    key: value
                    for key, value in proposal.__dict__.items()
                    # Exclude id and _sa_instance_state because they're unique to each table
                    if key != "_sa_instance_state" and key != "id"
                    # Exclude voters and finance_recipients because they are attached to another ORM
                    # session, and also we need to recreate them in the history DB with their unique ids
                    and key != "voters" and key != "finance_recipients"
                }

                # Retrieving voting message to save URL
                voting_message = await get_message(
                    client, VOTING_CHANNEL_ID, proposal.voting_message_id
                )
                # Create a history item
                history_item = ProposalHistory(
                    **proposal_dict,
                    result=result.value,
                    voting_message_url=voting_message.jump_url,
                    # Retrieve author nickname by ID, so it can be used quickly when exporting analytics
                    author_nickname=await get_nickname_by_id_or_mention(proposal.author_id),
                )
                # Add a history item
                DBUtil.session_history.add(history_item)
                # Flush the changes so to assign id to the history proposal and associate other objects with it later
                DBUtil.session_history.flush()

                # Make a copy of the voters
                copied_voters = []
                for voter in proposal.voters:
                    copied_voter = Voters(
                        user_id=voter.user_id,
                        user_nickname=await get_nickname_by_id_or_mention(voter.user_id),
                        value=voter.value,
                        voting_message_id=voter.voting_message_id,
                        proposal_id=history_item.id,
                    )
                    copied_voters.append(copied_voter)
                # Add the copied voters to the Voters table
                DBUtil.session_history.add_all(copied_voters)

                # Make a copy of the recipients
                copied_recipients = []
                for recipient in proposal.finance_recipients:
                    copied_recipient = FinanceRecipients(
                        proposal_id=history_item.id,
                        recipient_ids=recipient.recipient_ids,
                        recipient_nicknames=recipient.recipient_nicknames,
                        amount=recipient.amount,
                    )
                    copied_recipients.append(copied_recipient)
                # Add the copied recipients to the FinanceRecipients table
                DBUtil.session_history.add_all(copied_recipients)

                # Create a mapping of ids to nicknames
                id_to_nickname_map = {}
                for recipient in copied_recipients:
                    ids = recipient.recipient_ids.split(DB_ARRAY_COLUMN_SEPARATOR)
                    nicknames = recipient.recipient_nicknames.split(COMMA_LIST_SEPARATOR)
                    id_to_nickname_map.update(zip(ids, nicknames))
                # Replace all mentions in description with the actual nicknames
                # Once I faced a bug during recovery when cancelling proposals, that the description got empty for unknown reason, so we do null checks just in case
                if history_item.description and id_to_nickname_map:
                    history_item.description = replace_mentions_with_nicknames(
                        history_item.description, id_to_nickname_map
                    )

                # Save the changes
                DBUtil.session_history.commit()
                logger.debug(
                    "Added history item %s",
                    history_item,
                )
        except Exception as e:
            try:
                grant_channel = client.get_channel(GRANT_APPLY_CHANNEL_ID)
                await grant_channel.send(
                    f"An unexpected error occurred when saving proposal history. cc {RESPONSIBLE_MENTION}"
                )
            except Exception as e:
                logger.critical("Unable to reply in the chat that a critical error has occurred.")

            logger.critical(
                "Unexpected error in %s while saving proposal history, result=%s, proposal=%s",
                __name__,
                result,
                proposal,
                exc_info=True,
            )

    async def save(self):
        async with DBUtil.session_lock:
            DBUtil.session.commit()
