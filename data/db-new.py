"""Add new fields to LegalRegulation table based on custom format

Revision ID: add_legal_regulation_custom_fields
Revises: add_legal_regulation_fields
Create Date: 2025-03-23 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_legal_regulation_custom_fields'
down_revision = 'add_legal_regulation_fields'
branch_labels = None
depends_on = None


def upgrade():
    # 添加新字段
    op.add_column('legal_regulation', sa.Column('approved_by', sa.String(100), nullable=True))
    op.add_column('legal_regulation', sa.Column('revision_date', sa.DateTime(), nullable=True))
    op.add_column('legal_regulation', sa.Column('province', sa.String(50), nullable=True))
    op.add_column('legal_regulation', sa.Column('city', sa.String(50), nullable=True))


def downgrade():
    # 回滚修改
    op.drop_column('legal_regulation', 'approved_by')
    op.drop_column('legal_regulation', 'revision_date')
    op.drop_column('legal_regulation', 'province')
    op.drop_column('legal_regulation', 'city')
