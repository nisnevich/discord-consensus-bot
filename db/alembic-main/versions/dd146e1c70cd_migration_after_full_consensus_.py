"""Migration after full consensus implementation

Revision ID: dd146e1c70cd
Revises: 
Create Date: 2023-03-18 22:53:46.260794

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'dd146e1c70cd'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Drop the voters_temp table if it exists
    conn = op.get_bind()
    if conn.dialect.has_table(conn, 'voters_temp'):
        op.drop_table('voters_temp')
    # Create a new voters_temp table with the desired structure
    op.create_table(
        'voters_temp',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('user_id', sa.Integer),
        sa.Column('voting_message_id', sa.Integer),
        sa.Column('proposal_id', sa.Integer, sa.ForeignKey('proposals.id')),
        sa.Column('value', sa.String),
    )

    # Copy data from the old voters table to the new voters_temp table
    op.execute(
        """
        INSERT INTO voters_temp (id, user_id, voting_message_id, proposal_id, value)
        SELECT id, user_id, voting_message_id, grant_proposal_id, NULL
        FROM voters;
    """
    )

    # Drop the old voters table and rename the voters_temp table to voters
    op.drop_table('voters')
    op.rename_table('voters_temp', 'voters')


def downgrade():
    # Drop the voters_temp table if it exists
    conn = op.get_bind()
    if conn.dialect.has_table(conn, 'voters_temp'):
        op.drop_table('voters_temp')
    # Create a new voters_temp table with the old structure
    op.create_table(
        'voters_temp',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('user_id', sa.Integer),
        sa.Column('voting_message_id', sa.Integer),
        sa.Column('grant_proposal_id', sa.Integer, sa.ForeignKey('proposals.id')),
    )

    # Copy data from the current voters table to the new voters_temp table
    op.execute(
        """
        INSERT INTO voters_temp (id, user_id, voting_message_id, grant_proposal_id)
        SELECT id, user_id, voting_message_id, proposal_id
        FROM voters;
    """
    )

    # Drop the current voters table and rename the voters_temp table to voters
    op.drop_table('voters')
    op.rename_table('voters_temp', 'voters')
