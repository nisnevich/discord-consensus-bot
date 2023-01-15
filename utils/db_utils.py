
from utils import const

from schemas.grant_proposals import Base, GrantProposals
from sqlalchemy.orm import sessionmaker

import sqlalchemy


class DBUtil:

    def __init__(self):
        self.engine = None

        # Connect to the database
        self.connect_db()

        # Create the Session
        Session = sessionmaker(bind=self.engine)
        self.session = Session()

    def connect_db(self):
        if self.engine is None:
            self.engine = sqlalchemy.create_engine(f'sqlite:///{const.DB_NAME}')
    
    def create_all_tables(self):
        Base.metadata.create_all(self.engine)

    def close_db(self):
        self.engine.close_db()

    def load_pending_grant_proposals(self):
        return self.session.query(GrantProposals)

    def query(self):
        """
        Do ORM querying here, or we can also create standalone methods to
        run different queries for different purposes.
        """
        pass
