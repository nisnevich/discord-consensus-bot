from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String

from utils.const import GRANT_PROPOSALS_TABLE_NAME

Base = declarative_base()


class GrantProposals(Base):
    __tablename__ = GRANT_PROPOSALS_TABLE_NAME

    id = Column(Integer, primary_key=True)
    message_id = Column(Integer)
    channel_id = Column(Integer)
    mention = Column(String)
    amount = Column(Integer)
    description = Column(String)
    timer = Column(Integer)

    def __repr__(self) -> str:
        return f"<GrantProposal(id={self.id}, message_id={self.message_id}, channel_id={self.channel_id}, mention={self.mention}, amount={self.amount}, description={self.description}, timer={self.timer}>"