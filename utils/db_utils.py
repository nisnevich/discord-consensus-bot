from utils import const
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import Query
from sqlalchemy import create_engine
from schemas.grant_proposals import Base, GrantProposals


class DBUtil:
    def __init__(self):
        self.engine = None
        self.session = None
        self.connect_db()

    def connect_db(self):
        self.engine = create_engine(f'sqlite:///{const.DB_NAME}')
        self.session = sessionmaker(bind=self.engine)()

    def create_all_tables(self):
        if "grant_proposals" not in Base.metadata.tables:
            Base.metadata.create_all(self.engine)
        else:
            print("Tables already exist.")

    def close_db(self):
        self.engine.dispose()

    def load_pending_grant_proposals(self) -> Query:
        return self.session.query(GrantProposals)
