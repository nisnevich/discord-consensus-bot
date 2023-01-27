from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy import Column, Integer, String, ForeignKey

from utils.const import GRANT_PROPOSALS_TABLE_NAME, VOTERS_TABLE_NAME

Base = declarative_base()


class GrantProposals(Base):
    __tablename__ = GRANT_PROPOSALS_TABLE_NAME

    id = Column(Integer, primary_key=True)
    message_id = Column(Integer)
    channel_id = Column(Integer)
    author = Column(Integer)
    voting_message_id = Column(Integer)
    mention = Column(String)
    amount = Column(Integer)
    description = Column(String)
    timer = Column(Integer)
    """
    In the next line, back_populates creates a bidirectional relationship between the two classes.
    cascade specifies what should happen to the related voters when the grant proposal is deleted.
    "all" means that all actions, such as deletion, will be cascaded to the related voters.
    "delete-orphan" means that any voters that no longer have a related grant proposal will be deleted from the database.
    """
    voters = relationship(
        "Voters", back_populates=GRANT_PROPOSALS_TABLE_NAME, cascade="all, delete-orphan"
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.voters = []

    def __repr__(self) -> str:
        return f"<GrantProposal(id={self.id}, message_id={self.message_id}, author={self.author}, channel_id={self.channel_id}, mention={self.mention}, amount={self.amount}, description={self.description}, timer={self.timer}, voters={self.voters}>"


class Voters(Base):
    """
    The Voters class represents a voter in a grant proposal. It is used to store user_id and grant_proposal_id in the 'voters' table in the database. The grant_proposal_id is a foreign key referencing the 'grant_proposals' table, and is used to establish a relationship between a voter and the grant proposal they voted against. This relationship is defined using SQLAlchemy's relationship feature, and allows for easy retrieval of all voters for a specific grant proposal.
    """

    __tablename__ = VOTERS_TABLE_NAME
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    grant_proposal_id = Column(Integer, ForeignKey("grant_proposals.id"))

    grant_proposal = relationship("GrantProposals", back_populates=VOTERS_TABLE_NAME)

    def __repr__(self) -> str:
        return f"<Voter(id={self.id}, user_id={self.user_id}, grant_proposal_id={self.grant_proposal_id}>"
