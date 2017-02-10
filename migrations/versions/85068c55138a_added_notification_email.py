"""Added Notification Email

Revision ID: 85068c55138a
Revises: 32dec7b290bb
Create Date: 2017-02-08 11:32:30.575164

"""

# revision identifiers, used by Alembic.
revision = '85068c55138a'
down_revision = '32dec7b290bb'

from alembic import op
import sqlalchemy as sa


def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.add_column('users', sa.Column('notification_email', sa.String(length=254), nullable=True))
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('users', 'notification_email')
    ### end Alembic commands ###
