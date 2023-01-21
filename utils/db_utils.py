import atexit
import logging
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
    def __init__(self):
        self.engine = None
        self.session = None
        self.connect_db()

    def connect_db(self):
        self.engine = create_engine(f'sqlite:///{DB_NAME}')
        self.session = sessionmaker(bind=self.engine)()
        # run close_db once execution finishes
        atexit.register(self.close_db)

    def create_all_tables(self):
        if not self.engine.has_table(GRANT_PROPOSALS_TABLE_NAME):
            Base.metadata.create_all(self.engine)
        else:
            logger.info("Tables already exist: %s", GRANT_PROPOSALS_TABLE_NAME)

    def close_db(self):
        self.engine.dispose()

    def load_pending_grant_proposals(self) -> Query:
        return self.session.query(GrantProposals)
