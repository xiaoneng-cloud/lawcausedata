"""Add new fields to LegalRegulation

Revision ID: 5e509aab697a
Revises: 1cd8a2fed24b
Create Date: 2025-03-23 10:37:48.888502

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5e509aab697a'
down_revision = '1cd8a2fed24b'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('order_item')
    op.drop_table('supplier')
    op.drop_table('category')
    op.drop_table('product')
    op.drop_table('order')
    with op.batch_alter_table('legal_regulation', schema=None) as batch_op:
        batch_op.add_column(sa.Column('issued_by', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('document_number', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('hierarchy_level', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('industry_category', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('validity', sa.String(length=20), nullable=True))
        batch_op.drop_column('source')

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('legal_regulation', schema=None) as batch_op:
        batch_op.add_column(sa.Column('source', sa.VARCHAR(length=100), nullable=True))
        batch_op.drop_column('validity')
        batch_op.drop_column('industry_category')
        batch_op.drop_column('hierarchy_level')
        batch_op.drop_column('document_number')
        batch_op.drop_column('issued_by')

    op.create_table('order',
    sa.Column('id', sa.INTEGER(), nullable=False),
    sa.Column('order_number', sa.VARCHAR(length=50), nullable=True),
    sa.Column('order_date', sa.DATETIME(), nullable=True),
    sa.Column('status', sa.VARCHAR(length=20), nullable=True),
    sa.Column('total_amount', sa.FLOAT(), nullable=True),
    sa.Column('notes', sa.TEXT(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('order_number')
    )
    op.create_table('product',
    sa.Column('id', sa.INTEGER(), nullable=False),
    sa.Column('name', sa.VARCHAR(length=200), nullable=False),
    sa.Column('description', sa.TEXT(), nullable=True),
    sa.Column('price', sa.FLOAT(), nullable=False),
    sa.Column('stock', sa.INTEGER(), nullable=True),
    sa.Column('category_id', sa.INTEGER(), nullable=False),
    sa.Column('created_at', sa.DATETIME(), nullable=True),
    sa.Column('updated_at', sa.DATETIME(), nullable=True),
    sa.ForeignKeyConstraint(['category_id'], ['category.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('category',
    sa.Column('id', sa.INTEGER(), nullable=False),
    sa.Column('name', sa.VARCHAR(length=100), nullable=False),
    sa.Column('description', sa.TEXT(), nullable=True),
    sa.Column('created_at', sa.DATETIME(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_table('supplier',
    sa.Column('id', sa.INTEGER(), nullable=False),
    sa.Column('name', sa.VARCHAR(length=200), nullable=False),
    sa.Column('contact_person', sa.VARCHAR(length=100), nullable=True),
    sa.Column('email', sa.VARCHAR(length=100), nullable=True),
    sa.Column('phone', sa.VARCHAR(length=20), nullable=True),
    sa.Column('address', sa.TEXT(), nullable=True),
    sa.Column('active', sa.BOOLEAN(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('order_item',
    sa.Column('id', sa.INTEGER(), nullable=False),
    sa.Column('order_id', sa.INTEGER(), nullable=False),
    sa.Column('product_id', sa.INTEGER(), nullable=False),
    sa.Column('quantity', sa.INTEGER(), nullable=True),
    sa.Column('price', sa.FLOAT(), nullable=False),
    sa.ForeignKeyConstraint(['order_id'], ['order.id'], ),
    sa.ForeignKeyConstraint(['product_id'], ['product.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###
