"""add video_status to campaigns

Revision ID: a1b2c3d4e5f6
Revises: e318b872c617
Create Date: 2026-05-10 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f6'
down_revision = 'e318b872c617'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('campaigns', sa.Column('video_status', sa.String(length=20), nullable=True))


def downgrade():
    op.drop_column('campaigns', 'video_status')
