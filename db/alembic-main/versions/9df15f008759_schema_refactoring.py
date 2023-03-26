"""Schema refactoring

Revision ID: 9df15f008759
Revises: dd146e1c70cd
Create Date: 2023-03-19 16:36:16.530123

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9df15f008759'
down_revision = 'dd146e1c70cd'
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

    # Drop 'author', 'threshold', 'mention' columns from 'proposals' table
    op.drop_column('proposals', 'author')
    op.drop_column('proposals', 'threshold')
    op.drop_column('proposals', 'mention')


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('proposals', sa.Column('mention', sa.VARCHAR(), nullable=True))
    op.add_column('proposals', sa.Column('threshold', sa.INTEGER(), nullable=True))
    op.add_column('proposals', sa.Column('author', sa.VARCHAR(), nullable=True))
    op.drop_column('proposals', 'threshold_negative')
    op.drop_column('proposals', 'recipient_ids')
    op.drop_column('proposals', 'author_id')
    op.drop_column('proposal_history', 'recipient_nicknames')
    op.drop_column('proposal_history', 'author_nickname')
    # ### end Alembic commands ###
