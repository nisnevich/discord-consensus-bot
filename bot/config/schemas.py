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
    PROPOSALS_TABLE_NAME,
    VOTERS_TABLE_NAME,
    PROPOSAL_HISTORY_TABLE_NAME,
    FREE_FUNDING_TRANSACTIONS_TABLE_NAME,
    FREE_FUNDING_BALANCES_TABLE_NAME,
    Vote,
    FINANCE_RECIPIENTS_TABLE_NAME,
)

Base = declarative_base()


class Proposals(Base):
    """
    A class representing proposals in the bot. It stores information about each proposal, such as
    its author, description, finance recipients, voters, and more.
    """

    __tablename__ = PROPOSALS_TABLE_NAME

    id = Column(Integer, primary_key=True)
    # The id of the initial message that submitted a proposal
    message_id = Column(Integer)
    # The id of the initial channel where the proposal was submitted
    channel_id = Column(Integer)
    # The id of the author of the proposal
    author_id = Column(Integer)
    # The id of the voting message in the channel VOTING_CHANNEL_ID
    voting_message_id = Column(Integer)
    # The text description of the proposal (validated to fit between MIN_DESCRIPTION_LENGTH and MAX_DESCRIPTION_LENGTH)
    description = Column(String)
    # Date and time when the proposal was submitted
    submitted_at = Column(DateTime)
    # Date and time when the proposal should be closed
    closed_at = Column(DateTime)
    # This is only needed for some error handling, though very helpful for onboarding new users
    bot_response_message_id = Column(Integer)

    # Defines whether the proposal has a grant to give or not
    not_financial = Column(Boolean)
    # For financial proposals, the total amount to be transferred
    total_amount = Column(
        Float, CheckConstraint('total_amount > -1000000000 AND total_amount < 1000000000')
    )

    # Reserved for later:
    # Minimal number of voters "against" needed to cancel this proposal
    threshold_negative = Column(Integer)
    # Minimal number of voters "for" in order for a proposal to pass; -1 if the full consensus is disabled for this proposal
    threshold_positive = Column(Integer)

    # Reserved for future usage
    # Holds ProposalVotingAnonymityType value
    anonymity_type = Column(Integer)
    # Holds ProposalVotingType value
    proposal_type = Column(Integer)
    # Maximum number of choices that a user can make (for ProposalVotingType.MULTI_CHOICE)
    number_of_choices_allowed = Column(Integer)
    # Array of voting options to choose from (Vote class values separated by DB_ARRAY_COLUMN_SEPARATOR)
    vote_options = Column(String)

    """
    In the next line, back_populates creates a bidirectional relationship between the two classes,
    the value is the name of the corresponding column in the related table.
    cascade specifies what should happen to the related voters when the grant proposal is deleted.
    "all" means that all actions, such as deletion, will be cascaded to the related voters.
    "delete-orphan" means that any voters that no longer have a related grant proposal will be deleted from the database.
    """
    voters = relationship("Voters", back_populates="proposal", cascade="all, delete-orphan")
    finance_recipients = relationship(
        "FinanceRecipients", back_populates="proposal", cascade="all, delete-orphan"
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.voters = []
        self.finance_recipients = []

    def __repr__(self):
        return f"<Proposal(id={self.id}, message_id={self.message_id}, channel_id={self.channel_id}, author_id={self.author_id}, voting_message_id={self.voting_message_id}, description={self.description}, submitted_at={self.submitted_at}, closed_at={self.closed_at}, bot_response_message_id={self.bot_response_message_id}, not_financial={self.not_financial}, total_amount={self.total_amount}, threshold_negative={self.threshold_negative}, threshold_positive={self.threshold_positive}, voters={self.voters}, finance_recipients={self.finance_recipients})>"


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
    # The authors nickname (used for analytics; the authors id is stored in the associated proposal)
    author_nickname = Column(String)

    # Add an index on the result column to optimise read query perfomance
    __table_args__ = (Index("ix_result", result),)

    def __repr__(self):
        return f"<ProposalHistory(id={self.id}, message_id={self.message_id}, channel_id={self.channel_id}, author_id={self.author_id}, voting_message_id={self.voting_message_id}, description={self.description}, submitted_at={self.submitted_at}, closed_at={self.closed_at}, bot_response_message_id={self.bot_response_message_id}, not_financial={self.not_financial}, total_amount={self.total_amount}, threshold_negative={self.threshold_negative}, threshold_positive={self.threshold_positive}, voters={self.voters}, finance_recipients={self.finance_recipients}, result={self.result}, voting_message_url={self.voting_message_url}, author_nickname={self.author_nickname})>"


class FinanceRecipients(Base):
    """
    This class represents the finance recipients associated with a proposal. Each instance
    stores the recipient IDs and the corresponding amount they are to receive.
    """

    __tablename__ = FINANCE_RECIPIENTS_TABLE_NAME

    # Primary key
    id = Column(Integer, primary_key=True)
    # Foreign key - the proposal ID associated with the grant recipients
    proposal_id = Column(Integer, ForeignKey('proposals.id'))
    # The ids of the recipients
    recipient_ids = Column(String, nullable=False)
    # Comma-separated list of user nicknames to whom funds were sent
    recipient_nicknames = Column(String)
    # The amount to receive
    amount = Column(
        Float, CheckConstraint('amount > -1000000000 AND amount < 1000000000'), nullable=False
    )

    proposal = relationship("Proposals", back_populates="finance_recipients")

    def __repr__(self):
        return f"FinanceRecipients(id={self.id}, proposal_id={self.proposal_id},  recipient_ids={self.recipient_ids}, recipient_nicknames={self.recipient_nicknames}, amount={self.amount})"


class Voters(Base):
    """
    The Voters class represents a voter in a grant proposal. It is used to store user_id and proposal_id in the 'voters' table in the database. The proposal_id is a foreign key referencing the 'proposals' table, and is used to establish a relationship between a voter and the grant proposal they voted against. This relationship is defined using SQLAlchemy's relationship feature, and allows for easy retrieval of all voters for a specific grant proposal.
    """

    __tablename__ = VOTERS_TABLE_NAME
    # Primary key
    id = Column(Integer, primary_key=True)
    # Foreign key - the proposal ID associated with the voters
    proposal_id = Column(Integer, ForeignKey("proposals.id"))
    # User ID of the voter
    user_id = Column(Integer)
    # The nickname of the voter (used for analytics)
    user_nickname = Column(String)
    # ID of the voting message
    voting_message_id = Column(Integer)
    # A value of the vote, as per Vote enum
    value = Column(Integer)

    # Bidirectional relationship with the proposals
    proposal = relationship("Proposals", back_populates="voters")

    def __repr__(self) -> str:
        return f"<Voter(id={self.id}, user_id={self.user_id}, voting_message_id={self.voting_message_id}, proposal_id={self.proposal_id}, value={self.value})>"


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
    transaction, such as its author, recipient(s), total amount, description, and more. This class is
    aimed mainly to track free funding transactions, and is used to export statistics.
    """

    __tablename__ = FREE_FUNDING_TRANSACTIONS_TABLE_NAME

    id = Column(Integer, primary_key=True)
    # The ID of the author who sends the transaction
    author_id = Column(Integer)
    # The nickname of the user who sends transactions (used for analytics)
    author_nickname = Column(String)
    # List of comma-separated user ids to whom the funds were sent (the separator is defined in FREE_FUNDING_MENTIONS_COLUMN_SEPARATOR)
    recipient_ids = Column(String)
    # Comma-separated list of user nicknames to whom funds were sent (used for analytics)
    recipient_nicknames = Column(String)
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
        return f"<FreeFundingTransaction(id={self.id}, author_id={self.author_id}, author_nickname={self.author_nickname}, recipient_ids={self.recipient_ids}, recipient_nicknames={self.recipient_nicknames}, total_amount={self.total_amount}, description={self.description}, submitted_at={self.submitted_at}, message_url={self.message_url})>"
