import atexit
import asyncio
import datetime
import os

from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import Query
from sqlalchemy import create_engine

from bot.config.schemas import Base, Proposals, ProposalHistory
from bot.config.logging_config import log_handler, console_handler
from bot.config.const import *

logger = logging.getLogger(__name__)
logger.setLevel(DEFAULT_LOG_LEVEL)
logger.addHandler(log_handler)
logger.addHandler(console_handler)


class DBUtil:
    engine = None
    session = None
    # The lock is used to prevent concurrency errors when updating DB from event loop coroutines
    session_lock = asyncio.Lock()

    def connect_db(self):
        if DBUtil.engine is None:
            DBUtil.engine = create_engine(f"sqlite:///{DB_PATH}")
        if DBUtil.session is None:
            DBUtil.session = sessionmaker(bind=DBUtil.engine)()
        # run close_db once the main thread exits
        atexit.register(self.close_db)

    def close_db(self):
        DBUtil.engine.dispose()

    def create_all_tables(self):
        if not DBUtil.engine.has_table(GRANT_PROPOSALS_TABLE_NAME):
            Base.metadata.create_all(DBUtil.engine)
        else:
            logger.info("Table already exist: %s", GRANT_PROPOSALS_TABLE_NAME)
        if not DBUtil.engine.has_table(VOTERS_TABLE_NAME):
            Base.metadata.create_all(DBUtil.engine)
        else:
            logger.info("Table already exist: %s", VOTERS_TABLE_NAME)
        if not DBUtil.engine.has_table(PROPOSAL_HISTORY_TABLE_NAME):
            Base.metadata.create_all(DBUtil.engine)
        else:
            logger.info("Table already exist: %s", PROPOSAL_HISTORY_TABLE_NAME)

    def load_pending_grant_proposals(self) -> Query:
        return DBUtil.session.query(Proposals)

    def log_pending_grant_proposals(self) -> Query:
        # Load pending proposals from database
        pending_grant_proposals = self.load_pending_grant_proposals()
        logger.info("Logging pending proposals in DB on request")
        logger.info("Total: %d", pending_grant_proposals.count())
        for proposal in pending_grant_proposals:
            logger.info(proposal)

    async def filter(self, table, condition):
        async with DBUtil.session_lock:
            query = DBUtil.session.query(table)
            return query.filter(condition).first()

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

    async def add_history_item(self, proposal, result):
        """
        Adds a proposal to the ProposalHistory table after it has been processed.

        Parameters:
        proposal (Proposals): The original proposal that needs to be added to the history.
        result (ProposalResult): The result of the proposal. This should be one of the enumerated values in `ProposalResult`.
        """
        async with DBUtil.session_lock:
            # FIXME replace this check
            for key, value in proposal.__dict__.items():
                if value is None:
                    logger.critical(f"NONE VALUE FOUND {key}: {value}")
            # Copy all attributes from Proposals table excluding some of them
            proposal_dict = {
                key: value
                for key, value in proposal.__dict__.items()
                if key != "_sa_instance_state" and key != "id"
            }
            DBUtil.session.add(
                ProposalHistory(
                    **proposal_dict,
                    result=result.value,
                    closed_at=datetime.datetime.utcnow(),
                )
            )
            DBUtil.session.commit()

    async def commit(self):
        async with DBUtil.session_lock:
            DBUtil.session.commit()
