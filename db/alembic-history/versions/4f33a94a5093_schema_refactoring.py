"""Schema refactoring

Revision ID: 4f33a94a5093
Revises: b8de8b75b156
Create Date: 2023-03-19 17:27:39.885526

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4f33a94a5093'
down_revision = 'b8de8b75b156'
branch_labels = None
depends_on = None


def upgrade():
    # Add 'author_nickname', 'recipient_nicknames' columns to 'proposal_history' table
    op.add_column('proposal_history', sa.Column('author_nickname', sa.String(), nullable=True))
    op.add_column('proposal_history', sa.Column('recipient_nicknames', sa.String(), nullable=True))

    # Add 'author_id', 'recipient_ids', 'threshold_negative' columns to 'proposals' table
    op.add_column('proposals', sa.Column('author_id', sa.Integer(), nullable=True))
    op.add_column('proposals', sa.Column('recipient_ids', sa.String(), nullable=True))
    op.add_column('proposals', sa.Column('threshold_negative', sa.Integer(), nullable=True))

    # Copy 'author' values to 'author_nickname' and 'mention' values to 'recipient_nicknames'
    op.execute(
        """
        UPDATE proposal_history
        SET author_nickname = (
            SELECT author
            FROM proposals
            WHERE proposals.id = proposal_history.id
        ),
        recipient_nicknames = (
            SELECT mention
            FROM proposals
            WHERE proposals.id = proposal_history.id
        )
    """
    )

    # Drop 'author', 'threshold', 'mention' columns from 'proposals' table
    op.drop_column('proposals', 'author')
    op.drop_column('proposals', 'threshold')
    op.drop_column('proposals', 'mention')


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'voters', type_='foreignkey')
    op.create_foreign_key(
        'fk_voters_proposal_id', 'voters', 'proposals', ['proposal_id'], ['id'], ondelete='CASCADE'
    )
    op.add_column('proposals', sa.Column('author', sa.VARCHAR(), nullable=True))
    op.add_column('proposals', sa.Column('threshold', sa.INTEGER(), nullable=True))
    op.add_column('proposals', sa.Column('mention', sa.VARCHAR(), nullable=True))
    op.drop_column('proposals', 'threshold_negative')
    op.drop_column('proposals', 'recipient_ids')
    op.drop_column('proposals', 'author_id')
    op.drop_column('proposal_history', 'recipient_nicknames')
    op.drop_column('proposal_history', 'author_nickname')
    # ### end Alembic commands ###
