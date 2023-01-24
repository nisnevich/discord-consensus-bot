import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from schemas.grant_proposals import Base, GrantProposals


class TestGrantProposals(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(self.engine)
        self.session = sessionmaker(bind=self.engine)()

    def test_grant_proposals_init(self):
        proposal = GrantProposals(
            message_id=1,
            channel_id=1,
            mention="@user",
            amount=100,
            description="Test proposal",
            timer=0,
        )

        self.assertEqual(proposal.message_id, 1)
        self.assertEqual(proposal.mention, "@user")
        self.assertEqual(proposal.amount, 100)
        self.assertEqual(proposal.description, "Test proposal")
        self.assertEqual(proposal.timer, 0)
        self.assertEqual(proposal.channel_id, 1)

    def test_grant_proposals_add_to_db(self):
        proposal = GrantProposals(
            message_id=1,
            mention="@user",
            amount=100,
            description="Test proposal",
            timer=0,
            channel_id=1,
        )
        self.session.add(proposal)
        self.session.commit()

        result = self.session.query(GrantProposals).first()
        self.assertEqual(result, proposal)

    def tearDown(self):
        Base.metadata.drop_all(self.engine)

    def test_cleanup_grant_proposal_and_votes():
        # Create a new grant proposal and associated votes
        grant_proposal = GrantProposals(
            message_id=1,
            channel_id=1,
            mention="test_user",
            amount=100,
            description="test_description",
            timer=60,
        )
        voters = [Voters(user_id=i, grant_proposal=grant_proposal) for i in range(5)]
        session.add(grant_proposal)
        session.add_all(voters)
        session.commit()
        proposal_id = grant_proposal.id
        vote_ids = [vote.id for vote in voters]

        # Check that the grant proposal and associated votes were added to the database
        assert session.query(GrantProposals).filter_by(id=proposal_id).count() == 1
        assert session.query(Voters).filter(Voters.id.in_(vote_ids)).count() == 5

        # Delete the grant proposal
        session.delete(grant_proposal)
        session.commit()

        # Check that the grant proposal and associated votes were removed from the database
        assert session.query(GrantProposals).filter_by(id=proposal_id).count() == 0
        assert session.query(Voters).filter(Voters.id.in_(vote_ids)).count() == 0


if __name__ == '__main__':
    unittest.main()
