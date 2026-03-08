"""add_compliance_gaps

Revision ID: 3ec8a9c999bf
Revises: 0e074134f897
Create Date: 2026-03-08 01:40:37.465211
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision: str = '3ec8a9c999bf'
down_revision: Union[str, None] = '0e074134f897'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


from sqlalchemy.dialects import postgresql

def upgrade() -> None:
    # We must explicitly create the Enum types in Postgres if they don't exist
    sa.Enum('identified', 'in_progress', 'resolved', 'accepted_risk', name='gapstatus').create(op.get_bind(), checkfirst=True)
    sa.Enum('critical', 'high', 'medium', 'low', name='gapseverity').create(op.get_bind(), checkfirst=True)

    op.create_table('compliance_gaps',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('scraped_content_id', postgresql.UUID(as_uuid=True), nullable=False),
        
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        
        sa.Column('status', postgresql.ENUM('identified', 'in_progress', 'resolved', 'accepted_risk', name='gapstatus', create_type=False), server_default='identified', nullable=False),
        sa.Column('severity', postgresql.ENUM('critical', 'high', 'medium', 'low', name='gapseverity', create_type=False), nullable=False),
        
        sa.Column('affected_modules', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=True),
        sa.Column('deadline', sa.Date(), nullable=True),
        sa.Column('is_new_requirement', sa.Boolean(), server_default='false', nullable=True),
        
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        
        sa.ForeignKeyConstraint(['scraped_content_id'], ['scraped_content.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_index(op.f('ix_comp_gaps_scraped'), 'compliance_gaps', ['scraped_content_id'], unique=False)
    op.create_index(op.f('ix_comp_gaps_severity'), 'compliance_gaps', ['severity'], unique=False)
    op.create_index(op.f('ix_comp_gaps_status'), 'compliance_gaps', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_comp_gaps_status'), table_name='compliance_gaps')
    op.drop_index(op.f('ix_comp_gaps_severity'), table_name='compliance_gaps')
    op.drop_index(op.f('ix_comp_gaps_scraped'), table_name='compliance_gaps')
    op.drop_table('compliance_gaps')
    
    sa.Enum(name='gapseverity').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='gapstatus').drop(op.get_bind(), checkfirst=True)
