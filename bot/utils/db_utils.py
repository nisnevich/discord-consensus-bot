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

    async def add(self, orm_object, is_history=False):
        """
        Adds object to db.
        """
        if is_history:
            async with DBUtil.session_lock_history:
                DBUtil.session_history.add(orm_object)
                DBUtil.session_history.commit()
        else:
            async with DBUtil.session_lock:
                DBUtil.session.add(orm_object)
                DBUtil.session.commit()

    async def add_all(self, orm_object, is_history=False):
        """
        Adds all objects from a given iterable to db.
        """
        if is_history:
            async with DBUtil.session_lock_history:
                DBUtil.session_history.add_all(orm_object)
                DBUtil.session_history.commit()
        else:
            async with DBUtil.session_lock:
                DBUtil.session.add_all(orm_object)
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

    async def save(self, is_history=False):
        if is_history:
            async with DBUtil.session_lock_history:
                DBUtil.session_history.commit()
        else:
            async with DBUtil.session_lock:
                DBUtil.session.commit()
