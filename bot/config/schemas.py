from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Float

from bot.config.const import GRANT_PROPOSALS_TABLE_NAME, VOTERS_TABLE_NAME

Base = declarative_base()


class Proposals(Base):
    __tablename__ = GRANT_PROPOSALS_TABLE_NAME

    id = Column(Integer, primary_key=True)
    message_id = Column(Integer)
    channel_id = Column(Integer)
    author = Column(Integer)
    voting_message_id = Column(Integer)
    is_grantless = Column(Boolean)
    mention = Column(String)
    amount = Column(Float)
    description = Column(String)
    timer = Column(Integer)
    # This is only needed for some error handling, though very helpful for onboarding new users
    bot_response_message_id = Column(Integer)

    """
    In the next line, back_populates creates a bidirectional relationship between the two classes.
    cascade specifies what should happen to the related voters when the grant proposal is deleted.
    "all" means that all actions, such as deletion, will be cascaded to the related voters.
    "delete-orphan" means that any voters that no longer have a related grant proposal will be deleted from the database.
    """
    voters = relationship("Voters", back_populates="grant_proposal", cascade="all, delete-orphan")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.voters = []

    def __repr__(self):
        return f"<Proposals(id='{self.id}', message_id='{self.message_id}', channel_id='{self.channel_id}', author='{self.author}', voting_message_id='{self.voting_message_id}', mention='{self.mention}', amount='{self.amount}', description='{self.description}', timer='{self.timer}', bot_response_message_id='{self.bot_response_message_id}')>"


class Voters(Base):
    """
    The Voters class represents a voter in a grant proposal. It is used to store user_id and grant_proposal_id in the 'voters' table in the database. The grant_proposal_id is a foreign key referencing the 'proposals' table, and is used to establish a relationship between a voter and the grant proposal they voted against. This relationship is defined using SQLAlchemy's relationship feature, and allows for easy retrieval of all voters for a specific grant proposal.
    """

    __tablename__ = VOTERS_TABLE_NAME
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    voting_message_id = Column(Integer)
    grant_proposal_id = Column(Integer, ForeignKey("proposals.id"))

    grant_proposal = relationship("Proposals", back_populates="voters")

    def __repr__(self) -> str:
        return f"<Voter(id={self.id}, user_id={self.user_id}, grant_proposal_id={self.grant_proposal_id}>"
