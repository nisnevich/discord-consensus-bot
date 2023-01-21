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


if __name__ == '__main__':
    unittest.main()
