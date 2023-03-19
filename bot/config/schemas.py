import datetime

from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    Float,
    CheckConstraint,
    Index,
)

from bot.config.const import (
    GRANT_PROPOSALS_TABLE_NAME,
    VOTERS_TABLE_NAME,
    PROPOSAL_HISTORY_TABLE_NAME,
    FREE_FUNDING_TRANSACTIONS_TABLE_NAME,
    FREE_FUNDING_BALANCES_TABLE_NAME,
    Vote,
)

Base = declarative_base()


class Proposals(Base):
    """
    A class representing grant proposals in the bot. It stores information about each proposal, such as its author, description, grant receivers, and more. It also maintains relationships with the associated Voters class for handling votes on proposals.
    """

    __tablename__ = GRANT_PROPOSALS_TABLE_NAME

    id = Column(Integer, primary_key=True)
    # The id of the initial message that submitted a proposal
    message_id = Column(Integer)
    # The id of the initial channel where the proposal was submitted
    channel_id = Column(Integer)
    # The id of the author of the proposal
    author_id = Column(Integer)
    # The id of the voting message in the channel VOTING_CHANNEL_ID
    voting_message_id = Column(Integer)
    # Defines whether the proposal has a grant or not
    is_grantless = Column(Boolean)
    # List of comma-separated user ids to give a grant to (empty when is_grantless is true)
    receiver_ids = Column(String)
    # Amount of the grant (empty when is_grantless is true)
    # Defining some constraints to avoid overflow
    amount = Column(Float, CheckConstraint('amount > -1000000000 AND amount < 1000000000'))
    # The text description of the proposal (validated to fit between MIN_DESCRIPTION_LENGTH and MAX_DESCRIPTION_LENGTH)
    description = Column(String)
    # Date and time when the proposal was submitted
    submitted_at = Column(DateTime)
    # Date and time when the proposal should be closed
    closed_at = Column(DateTime)
    # This is only needed for some error handling, though very helpful for onboarding new users
    bot_response_message_id = Column(Integer)

    # Reserved for later:
    # Minimal number of voters "against" needed to cancel this proposal
    threshold_negative = Column(Integer)
    # Minimal number of voters "for" in order for a proposal to pass; -1 if the full consensus is disabled for this proposal
    threshold_positive = Column(Integer)

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

    def __repr__(self):
        return f"<Proposal(id={self.id}, message_id={self.message_id}, channel_id={self.channel_id}, author_id={self.author_id}, voting_message_id={self.voting_message_id}, is_grantless={self.is_grantless}, receiver_ids={self.receiver_ids}, amount={self.amount}, description={self.description}, submitted_at={self.submitted_at}, closed_at={self.closed_at}, bot_response_message_id={self.bot_response_message_id}, threshold_negative={self.threshold_negative}, threshold_positive={self.threshold_positive})>"


class Voters(Base):
    """
    The Voters class represents a voter in a grant proposal. It is used to store user_id and proposal_id in the 'voters' table in the database. The proposal_id is a foreign key referencing the 'proposals' table, and is used to establish a relationship between a voter and the grant proposal they voted against. This relationship is defined using SQLAlchemy's relationship feature, and allows for easy retrieval of all voters for a specific grant proposal.
    """

    __tablename__ = VOTERS_TABLE_NAME
    id = Column(Integer, primary_key=True)
    # User ID of the voter
    user_id = Column(Integer)
    # ID of the voting message
    voting_message_id = Column(Integer)
    # ID of the proposal that the given voter has voted for
    proposal_id = Column(Integer, ForeignKey("proposals.id"))
    # A value of the vote, as per Vote enum
    value = Column(Integer)

    # Bidirectional relationship with the proposals
    proposals = relationship("Proposals", back_populates=VOTERS_TABLE_NAME)

    def __repr__(self) -> str:
        return f"<Voter(id={self.id}, user_id={self.user_id}, voting_message_id={self.voting_message_id}, proposal_id={self.proposal_id}, value={self.value})>"


class ProposalHistory(Proposals):
    """
    The `ProposalHistory` class is a subclass of the `Proposals` class. It represents the history of approved proposals and is stored in a separate table in the database.
    """

    __tablename__ = PROPOSAL_HISTORY_TABLE_NAME
    __mapper_args__ = {
        'polymorphic_identity': PROPOSAL_HISTORY_TABLE_NAME,
    }
    # ID of the corresponding proposal
    id = Column(Integer, ForeignKey('proposals.id'), primary_key=True)
    # The result of the proposal (as per ProposalResult enum)
    result = Column(Integer, default=None)
    # The URL of the voting message in Discord
    voting_message_url = Column(String)
    # The authors nickname
    author_nickname = Column(String)
    # List of comma-separated user nicknames who have received grants (empty when is_grantless is true)
    receiver_nicknames = Column(String)

    # Add an index on the result column to optimise read query perfomance
    __table_args__ = (Index("ix_result", result),)

    def __repr__(self):
        return f"<ProposalHistory(id={self.id}, message_id={self.message_id}, channel_id={self.channel_id}, author_id={self.author_id}, voting_message_id={self.voting_message_id}, is_grantless={self.is_grantless}, receiver_ids={self.receiver_ids}, amount={self.amount}, description={self.description}, submitted_at={self.submitted_at}, closed_at={self.closed_at}, bot_response_message_id={self.bot_response_message_id}, result={self.result}, voting_message_url={self.voting_message_url}, author_nickname={self.author_nickname}, receiver_nicknames={self.receiver_nicknames}, threshold_negative={self.threshold})>"


class FreeFundingBalance(Base):
    """
    A class representing the free funding balances of users in the bot. It stores information about
    each user's remaining balance, their ID, and their nickname. This class is used to track and
    manage the balances of users who participate in the free funding process.
    """

    __tablename__ = FREE_FUNDING_BALANCES_TABLE_NAME

    id = Column(Integer, primary_key=True)
    # The mention of the user who sends transactions
    author_id = Column(Integer)
    # The nickname of the user who sends transactions (so that analytics will be retrieved quickly, without the need to query Discord for nicknames)
    author_nickname = Column(String)
    # The remaining balance of the user
    balance = Column(Float)

    def __repr__(self):
        return f"<FreeFundingBalance(id={self.id}, author_id={self.author_id}, author_nickname={self.author_nickname}, balance={self.balance})>"


class FreeFundingTransaction(Base):
    """
    A class representing free funding transactions in the bot. It stores information about each
    transaction, such as its author, receiver(s), total amount, description, and more. This class is
    aimed mainly to track free funding transactions, and is used to export statistics.
    """

    __tablename__ = FREE_FUNDING_TRANSACTIONS_TABLE_NAME

    id = Column(Integer, primary_key=True)
    # The ID of the author who sends the transaction
    author_id = Column(Integer)
    # The nickname of the user who sends transactions
    author_nickname = Column(String)
    # List of comma-separated user ids to whom the funds were sent (the separator is defined in FREE_FUNDING_MENTIONS_COLUMN_SEPARATOR)
    receiver_ids = Column(String)
    # Comma-separated list of user nicknames to whom funds were sent
    receiver_nicknames = Column(String)
    # Total amount of funds - a sum of the amounts sent to each mentioned user (defining some constraints to avoid overflow)
    total_amount = Column(
        Float, CheckConstraint('total_amount > -1000000000 AND total_amount < 1000000000')
    )
    # The text description of the transaction (validated to fit between MIN_DESCRIPTION_LENGTH and MAX_DESCRIPTION_LENGTH)
    description = Column(String)
    # Date and time when the transaction was performed
    submitted_at = Column(DateTime)
    # URL of the message where transaction was send
    message_url = Column(String)

    def __repr__(self):
        return f"<FreeFundingTransaction(id={self.id}, author_id={self.author_id}, author_nickname={self.author_nickname}, receiver_ids={self.receiver_ids}, receiver_nicknames={self.receiver_nicknames}, total_amount={self.total_amount}, description={self.description}, submitted_at={self.submitted_at}, message_url={self.message_url})>"
