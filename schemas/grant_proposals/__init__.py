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
    voters = relationship("Voters", back_populates="grant_proposal", cascade="all, delete-orphan")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.voters = []

    def __repr__(self) -> str:
        return f"<GrantProposal(id={self.id}, message_id={self.message_id}, channel_id={self.channel_id}, mention={self.mention}, amount={self.amount}, description={self.description}, timer={self.timer}, voters={self.voters}>"


class Voters(Base):
    __tablename__ = "voters"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    grant_proposal_id = Column(Integer, ForeignKey("grant_proposals.id"))

    grant_proposal = relationship("GrantProposals", back_populates="voters")

    def __repr__(self) -> str:
        return f"<Voter(id={self.id}, user_id={self.user_id}, grant_proposal_id={self.grant_proposal_id}>"
