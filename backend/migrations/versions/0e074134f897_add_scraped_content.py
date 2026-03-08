"""add_scraped_content

Revision ID: 0e074134f897
Revises: cd782d62fcbf
Create Date: 2026-03-08 01:23:31.863111
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision: str = '0e074134f897'
down_revision: Union[str, None] = 'cd782d62fcbf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


from sqlalchemy.dialects import postgresql

def upgrade() -> None:
    op.create_table('scraped_content',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('url_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('content_text', sa.Text(), nullable=False),
        sa.Column('content_hash', sa.String(length=64), nullable=True),
        sa.Column('is_processed', sa.Boolean(), server_default=sa.text('false'), nullable=True),
        sa.Column('scraped_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['url_id'], ['compliance_rule_urls.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_scraped_content_url_id'), 'scraped_content', ['url_id'], unique=False)
    op.create_index(op.f('ix_scraped_content_processed'), 'scraped_content', ['is_processed'], unique=False)

def downgrade() -> None:
    op.drop_index(op.f('ix_scraped_content_processed'), table_name='scraped_content')
    op.drop_index(op.f('ix_scraped_content_url_id'), table_name='scraped_content')
    op.drop_table('scraped_content')
