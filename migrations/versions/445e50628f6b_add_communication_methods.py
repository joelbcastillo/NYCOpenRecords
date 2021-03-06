"""add communication methods

Revision ID: 445e50628f6b
Revises: c7f05adcf7d9
Create Date: 2018-04-09 18:14:44.367390

"""

# revision identifiers, used by Alembic.
revision = '445e50628f6b'
down_revision = '22b97712d5db'

from alembic import op
import sqlalchemy as sa


def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.create_table('communication_methods',
    sa.Column('response_id', sa.Integer(), nullable=False),
    sa.Column('method_id', sa.Integer(), nullable=False),
    sa.Column('method_type', sa.Enum('letters', 'emails', name='communication_method_type'), nullable=True),
    sa.ForeignKeyConstraint(['method_id'], ['responses.id'], ),
    sa.ForeignKeyConstraint(['response_id'], ['responses.id'], ),
    sa.PrimaryKeyConstraint('response_id', 'method_id')
    )
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('communication_methods')
    ### end Alembic commands ###
