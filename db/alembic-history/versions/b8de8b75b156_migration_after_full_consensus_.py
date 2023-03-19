"""Migration after full consensus implementation

Revision ID: b8de8b75b156
Revises: 
Create Date: 2023-03-18 23:15:23.906593

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b8de8b75b156'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Add 'threshold_positive' column to 'proposals' table
    op.add_column("proposals", sa.Column("threshold_positive", sa.Integer))

    # Rename 'grant_proposal_id' column to 'proposal_id' in 'voters' table
    op.alter_column("voters", "grant_proposal_id", new_column_name="proposal_id")

    # Add 'value' column to 'voters' table
    op.add_column("voters", sa.Column("value", sa.String))

    # Update foreign key constraint with CASCADE ondelete event
    with op.batch_alter_table("voters") as batch_op:
        batch_op.create_foreign_key(
            "fk_voters_proposal_id",
            "proposals",
            ["proposal_id"],
            ["id"],
            ondelete="CASCADE",
        )
