"""Add new columns to Proposals and Voters. It's the same as for main db, but without creating
foreign key constraints.

Revision ID: c281b54891e9
Revises: 
Create Date: 2023-03-16 16:34:35.959637

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c281b54891e9'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    proposals_table = sa.Table('proposals', sa.MetaData(), autoload_with=conn)
    if 'threshold_positive' not in proposals_table.columns:
        with op.batch_alter_table("proposals") as batch_op:
            batch_op.add_column(sa.Column('threshold_positive', sa.Integer(), nullable=True))

    voters_table = sa.Table('voters', sa.MetaData(), autoload_with=conn)
    if 'proposal_id' not in voters_table.columns and 'value' not in voters_table.columns:
        with op.batch_alter_table("voters") as batch_op:
            batch_op.add_column(sa.Column('proposal_id', sa.Integer(), nullable=True))
            batch_op.add_column(sa.Column('value', sa.String(), nullable=True))
            batch_op.drop_column('grant_proposal_id')


def downgrade():
    conn = op.get_bind()
    proposals_table = sa.Table('proposals', sa.MetaData(), autoload_with=conn)
    if 'threshold_positive' in proposals_table.columns:
        with op.batch_alter_table("proposals") as batch_op:
            batch_op.drop_column('threshold_positive')

    voters_table = sa.Table('voters', sa.MetaData(), autoload_with=conn)
    if 'proposal_id' in voters_table.columns and 'value' in voters_table.columns:
        with op.batch_alter_table("voters") as batch_op:
            batch_op.add_column(sa.Column('grant_proposal_id', sa.Integer(), nullable=True))
            batch_op.drop_column('value')
            batch_op.drop_column('proposal_id')
