"""Add step_id field to LegalRegulationVersion

Revision ID: 5954656dfc91
Revises: cf90b5dbae42
Create Date: 2025-04-04 16:26:57.971450

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5954656dfc91'
down_revision = 'cf90b5dbae42'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('legal_regulation', schema=None) as batch_op:
        batch_op.drop_column('step_id')

    with op.batch_alter_table('legal_regulation_version', schema=None) as batch_op:
        batch_op.add_column(sa.Column('step_id', sa.Integer(), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('legal_regulation_version', schema=None) as batch_op:
        batch_op.drop_column('step_id')

    with op.batch_alter_table('legal_regulation', schema=None) as batch_op:
        batch_op.add_column(sa.Column('step_id', sa.INTEGER(), nullable=True))

    # ### end Alembic commands ###
