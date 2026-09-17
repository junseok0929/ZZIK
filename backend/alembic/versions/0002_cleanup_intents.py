"""Durable scheduled file cleanup also recovers interrupted uploads."""
from alembic import op
import sqlalchemy as sa
revision='0002'
down_revision='0001'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('file_cleanup',sa.Column('not_before',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()))

def downgrade():
    op.drop_column('file_cleanup','not_before')
