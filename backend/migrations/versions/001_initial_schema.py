"""Initial database schema — creates all tables for the compliance platform.

Revision ID: 001_initial
Revises: None
Create Date: 2026-03-06
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- tenants ---
    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("descope_tenant_id", sa.String(255), unique=True, nullable=False),
        sa.Column("settings", postgresql.JSONB(), server_default="{}"),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()")),
    )
    op.create_index("ix_tenants_descope_tenant_id", "tenants", ["descope_tenant_id"])

    # --- regulations ---
    op.create_table(
        "regulations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source", sa.String(100), nullable=False),
        sa.Column("source_id", sa.String(500), nullable=True),
        sa.Column("title", sa.String(1000), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("raw_content", sa.Text(), nullable=True),
        sa.Column("source_url", sa.String(2000), nullable=True),
        sa.Column("ai_analysis", postgresql.JSONB(), server_default="{}"),
        sa.Column("relevance_score", sa.Float(), nullable=True),
        sa.Column("affected_areas", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb")),
        sa.Column("key_requirements", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb")),
        sa.Column("status", sa.Enum("proposed", "comment_period", "final_rule", "effective", "archived", name="regulationstatus"), nullable=False, server_default="proposed"),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("comment_deadline", sa.Date(), nullable=True),
        sa.Column("published_date", sa.Date(), nullable=True),
        sa.Column("cfr_references", postgresql.JSONB(), server_default="'[]'::jsonb"),
        sa.Column("agencies", postgresql.JSONB(), server_default="'[]'::jsonb"),
        sa.Column("document_type", sa.String(100), nullable=True),
        sa.Column("ingested_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()")),
    )
    op.create_index("ix_regulations_source_source_id", "regulations", ["source", "source_id"], unique=True)
    op.create_index("ix_regulations_relevance", "regulations", ["relevance_score"])
    op.create_index("ix_regulations_status", "regulations", ["status"])
    op.create_index("ix_regulations_effective_date", "regulations", ["effective_date"])

    # --- gap_analyses ---
    op.create_table(
        "gap_analyses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("regulation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("regulations.id"), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("severity", sa.Enum("critical", "high", "medium", "low", name="gapseverity"), nullable=False),
        sa.Column("status", sa.Enum("identified", "in_progress", "resolved", "accepted_risk", name="gapstatus"), nullable=False, server_default="identified"),
        sa.Column("affected_code", postgresql.JSONB(), server_default="'[]'::jsonb"),
        sa.Column("affected_components", postgresql.JSONB(), server_default="'[]'::jsonb"),
        sa.Column("assigned_team", sa.String(100), nullable=True),
        sa.Column("effort_hours", sa.Integer(), nullable=True),
        sa.Column("effort_story_points", sa.Integer(), nullable=True),
        sa.Column("jira_epic_key", sa.String(50), nullable=True),
        sa.Column("jira_epic_url", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()")),
    )
    op.create_index("ix_gaps_regulation", "gap_analyses", ["regulation_id"])
    op.create_index("ix_gaps_severity", "gap_analyses", ["severity"])
    op.create_index("ix_gaps_status", "gap_analyses", ["status"])
    op.create_index("ix_gaps_team", "gap_analyses", ["assigned_team"])

    # --- communications ---
    op.create_table(
        "communications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("regulation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("regulations.id"), nullable=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=True),
        sa.Column("type", sa.Enum("new_regulation", "compliance_update", "deadline_reminder", "resolution_notice", name="communicationtype"), nullable=False),
        sa.Column("subject", sa.String(500), nullable=False),
        sa.Column("content_html", sa.Text(), nullable=False),
        sa.Column("content_plain", sa.Text(), nullable=True),
        sa.Column("status", sa.Enum("draft", "pending_approval", "approved", "sent", "failed", name="communicationstatus"), nullable=False, server_default="draft"),
        sa.Column("approved_by", sa.String(255), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("recipient_count", sa.Integer(), server_default="0"),
        sa.Column("scheduled_send_at", sa.DateTime(), nullable=True),
        sa.Column("reminder_interval_days", sa.Integer(), nullable=True),
        sa.Column("next_reminder_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()")),
    )
    op.create_index("ix_comms_status", "communications", ["status"])
    op.create_index("ix_comms_tenant", "communications", ["tenant_id"])
    op.create_index("ix_comms_regulation", "communications", ["regulation_id"])

    # --- exec_reports ---
    op.create_table(
        "exec_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("week_end", sa.Date(), nullable=False),
        sa.Column("summary_html", sa.Text(), nullable=False),
        sa.Column("summary_plain", sa.Text(), nullable=True),
        sa.Column("metrics", postgresql.JSONB(), server_default="{}"),
        sa.Column("risks", postgresql.JSONB(), server_default="'[]'::jsonb"),
        sa.Column("highlights", postgresql.JSONB(), server_default="'[]'::jsonb"),
        sa.Column("sent_to", postgresql.JSONB(), server_default="'[]'::jsonb"),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_reports_week", "exec_reports", ["week_start"], unique=True)

    # --- subscriptions ---
    op.create_table(
        "subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("feature", sa.String(100), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("notification_email", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()")),
    )
    op.create_index("ix_subs_tenant_feature", "subscriptions", ["tenant_id", "feature"], unique=True)

    # --- integration_configs ---
    op.create_table(
        "integration_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("integration_type", sa.String(50), nullable=False),
        sa.Column("config", postgresql.JSONB(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()")),
    )
    op.create_index("ix_integrations_type", "integration_configs", ["integration_type"])

    # --- audit_logs ---
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.String(255), nullable=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(100), nullable=False),
        sa.Column("resource_id", sa.String(255), nullable=True),
        sa.Column("details", postgresql.JSONB(), server_default="{}"),
        sa.Column("ip_address", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_audit_user", "audit_logs", ["user_id"])
    op.create_index("ix_audit_tenant", "audit_logs", ["tenant_id"])
    op.create_index("ix_audit_action", "audit_logs", ["action"])
    op.create_index("ix_audit_created", "audit_logs", ["created_at"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("integration_configs")
    op.drop_table("subscriptions")
    op.drop_table("exec_reports")
    op.drop_table("communications")
    op.drop_table("gap_analyses")
    op.drop_table("regulations")
    op.drop_table("tenants")

    # Drop enums
    sa.Enum(name="regulationstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="gapseverity").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="gapstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="communicationtype").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="communicationstatus").drop(op.get_bind(), checkfirst=True)
