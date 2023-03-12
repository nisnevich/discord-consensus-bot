import atexit
import asyncio
import datetime
import discord
import os

from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import Query
from sqlalchemy import create_engine

from bot.config.schemas import Base, Proposals, ProposalHistory, FreeFundingBalance
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
        if not DBUtil.engine.has_table(GRANT_PROPOSALS_TABLE_NAME):
            Base.metadata.create_all(DBUtil.engine)
        else:
            logger.info("Table already exist: %s", GRANT_PROPOSALS_TABLE_NAME)
        if not DBUtil.engine.has_table(VOTERS_TABLE_NAME):
            Base.metadata.create_all(DBUtil.engine)
        else:
            logger.info("Table already exist: %s", VOTERS_TABLE_NAME)
        if not DBUtil.engine.has_table(FREE_FUNDING_BALANCES_TABLE_NAME):
            Base.metadata.create_all(DBUtil.engine)
        else:
            logger.info("Table already exist: %s", FREE_FUNDING_BALANCES_TABLE_NAME)

        # Creating tables that are used for history and analytics
        if not DBUtil.engine_history.has_table(GRANT_PROPOSALS_TABLE_NAME):
            Base.metadata.create_all(DBUtil.engine_history)
        else:
            logger.info("Table already exist: %s", GRANT_PROPOSALS_TABLE_NAME)
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

    def get_user_free_funding_balance(self, author_mention) -> Query:
        return DBUtil.session.query(FreeFundingBalance).filter_by(author=author_mention).first()

    def load_pending_grant_proposals(self) -> Query:
        return DBUtil.session.query(Proposals)

    def log_pending_grant_proposals(self) -> Query:
        # Load pending proposals from database
        pending_grant_proposals = self.load_pending_grant_proposals()
        logger.info("Logging pending proposals in DB on request")
        logger.info("Total: %d", pending_grant_proposals.count())
        for proposal in pending_grant_proposals:
            logger.info(proposal)

    async def filter(self, table, is_history=True, condition=None):
        """
        Filters the given ORM objects and returns a query (results should be retrieved using
        statements like .all() or .first()). The DB is chosen depending on is_history parameter.
        """
        if is_history:
            async with DBUtil.session_lock_history:
                query = DBUtil.session_history.query(table)
                if condition:
                    return query.filter(condition)
                else:
                    return query
        else:
            async with DBUtil.session_lock:
                query = DBUtil.session.query(table)
                if condition:
                    return query.filter(condition)
                else:
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
        async with DBUtil.session_lock_history:
            # Before writing to DB, we should modify some values using Discord API for them to be quickly retrieved when exporting analytics
            # Converting author id to nickname
            proposal.author = await get_nickname_by_id_or_mention(proposal.author)

            # If the proposal has a grant, the mentioned person id will be converted to a nickname
            if not proposal.is_grantless:
                proposal.mention = await get_nickname_by_id_or_mention(proposal.mention)
            # Retrieving voting message to save URL
            voting_message = await get_message(
                client, VOTING_CHANNEL_ID, proposal.voting_message_id
            )

            # Copy all attributes from Proposals table excluding some of them
            proposal_dict = {
                key: value
                for key, value in proposal.__dict__.items()
                if key != "_sa_instance_state" and key != "id" and key != "voters"
            }

            DBUtil.session_history.add(
                ProposalHistory(
                    **proposal_dict,
                    result=result.value,
                    voting_message_url=voting_message.jump_url,
                )
            )
            DBUtil.session_history.commit()

    async def save(self):
        async with DBUtil.session_lock:
            DBUtil.session.commit()
