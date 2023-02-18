import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from bot.config.schemas import Base, Proposals, Voters


class TestGrantProposals(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(self.engine)
        self.session = sessionmaker(bind=self.engine)()

    def test_grant_proposals_init(self):
        proposal = Proposals(
            message_id=1,
            channel_id=1,
            mention="@user",
            amount=100,
            description="Test proposal",
        )

        self.assertEqual(proposal.message_id, 1)
        self.assertEqual(proposal.mention, "@user")
        self.assertEqual(proposal.amount, 100)
        self.assertEqual(proposal.description, "Test proposal")
        self.assertEqual(proposal.channel_id, 1)

    def test_grant_proposals_add_to_db(self):
        proposal = Proposals(
            message_id=1,
            mention="@user",
            amount=100,
            description="Test proposal",
            channel_id=1,
        )
        self.session.add(proposal)
        self.session.commit()

        result = self.session.query(Proposals).first()
        self.assertEqual(result, proposal)

    def test_cleanup_grant_proposal_and_votes(self):  # Fix indentation
        # Create a new grant proposal and associated votes
        grant_proposal = Proposals(
            message_id=1,
            channel_id=1,
            mention="test_user",
            amount=100,
            description="test_description",
        )
        voters = [Voters(user_id=i, grant_proposal=grant_proposal) for i in range(5)]
        self.session.add(grant_proposal)
        self.session.add_all(voters)
        self.session.commit()
        proposal_id = grant_proposal.id
        vote_ids = [vote.id for vote in voters]

        # Check that the grant proposal and associated votes were added to the database
        assert self.session.query(Proposals).filter_by(id=proposal_id).count() == 1
        assert self.session.query(Voters).filter(Voters.id.in_(vote_ids)).count() == 5

        # Delete the grant proposal
        self.session.delete(grant_proposal)
        self.session.commit()

        # Check that the grant proposal and associated votes were removed from the database
        assert self.session.query(Proposals).filter_by(id=proposal_id).count() == 0
        assert self.session.query(Voters).filter(Voters.id.in_(vote_ids)).count() == 0


class TestVoters(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(self.engine)
        self.session = sessionmaker(bind=self.engine)()

    def test_voters_init(self):
        grant_proposal = Proposals(
            message_id=1,
            channel_id=1,
            mention="test_user",
            amount=100,
            description="test_description",
        )
        voter = Voters(user_id=1, grant_proposal=grant_proposal)

        self.assertEqual(voter.user_id, 1)
        self.assertEqual(voter.grant_proposal, grant_proposal)

    def test_voters_add_to_db(self):
        grant_proposal = Proposals(
            message_id=1,
            channel_id=1,
            mention="test_user",
            amount=100,
            description="test_description",
        )
        voter = Voters(user_id=1, grant_proposal=grant_proposal)
        self.session.add(voter)
        self.session.commit()

        result = self.session.query(Voters).first()
        self.assertEqual(result, voter)

    def test_cleanup_voters(self):
        # Create a new grant proposal and associated votes
        grant_proposal = Proposals(
            message_id=1,
            channel_id=1,
            mention="test_user",
            amount=100,
            description="test_description",
        )
        voters = [Voters(user_id=i, grant_proposal=grant_proposal) for i in range(5)]
        self.session.add(grant_proposal)
        self.session.add_all(voters)
        self.session.commit()
        vote_ids = [vote.id for vote in voters]

        # Check that the voters were added to the database
        assert self.session.query(Voters).filter(Voters.id.in_(vote_ids)).count() == 5

        # Delete the voters
        for vote in voters:
            self.session.delete(vote)
        self.session.commit()

        # Check that the voters were removed from the database
        assert self.session.query(Voters).filter(Voters.id.in_(vote_ids)).count() == 0

    def tearDown(self):
        Base.metadata.drop_all(self.engine)


if __name__ == '__main__':
    asynctest.main()
