import atexit
import logging
import asyncio
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import Query
from sqlalchemy import create_engine
from schemas.grant_proposals import Base, GrantProposals

from utils.const import DB_NAME, GRANT_PROPOSALS_TABLE_NAME
from utils.logging_config import log_handler, console_handler

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(log_handler)
logger.addHandler(console_handler)


class DBUtil:
    engine = None
    session = None
    session_lock = asyncio.Lock()

    def connect_db(self):
        if DBUtil.engine is None:
            DBUtil.engine = create_engine(f'sqlite:///{DB_NAME}')
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
            logger.info("Tables already exist: %s", GRANT_PROPOSALS_TABLE_NAME)

    def load_pending_grant_proposals(self) -> Query:
        return DBUtil.session.query(GrantProposals)

    def log_pending_grant_proposals(self) -> Query:
        # Load pending proposals from database
        pending_grant_proposals = self.load_pending_grant_proposals()
        logger.info("Logging pending proposals in DB on request")
        logger.info("Total: %d", pending_grant_proposals.count())
        for proposal in pending_grant_proposals:
            logger.info(proposal)

    async def add(self, orm_object):
        async with DBUtil.session_lock:
            DBUtil.session.add(orm_object)
            DBUtil.session.commit()

    async def delete(self, orm_object):
        async with DBUtil.session_lock:
            DBUtil.session.delete(orm_object)
            DBUtil.session.commit()

    async def commit(self):
        async with DBUtil.session_lock:
            DBUtil.session.commit()
