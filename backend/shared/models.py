"""SQLAlchemy models for the compliance platform database."""
import uuid
from datetime import datetime, date
from enum import Enum as PyEnum

from sqlalchemy import (
    Column,
    String,
    Text,
    Float,
    Integer,
    Boolean,
    DateTime,
    Date,
    ForeignKey,
    Enum,
    JSON,
    Index,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


# ---- Enums ----

class RegulationStatus(str, PyEnum):
    """Status of a tracked regulation."""
    PROPOSED = "proposed"
    COMMENT_PERIOD = "comment_period"
    FINAL_RULE = "final_rule"
    EFFECTIVE = "effective"
    ARCHIVED = "archived"


class GapSeverity(str, PyEnum):
    """Severity of a compliance gap."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class GapStatus(str, PyEnum):
    """Status of a gap analysis item."""
    IDENTIFIED = "identified"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    ACCEPTED_RISK = "accepted_risk"


class CommunicationStatus(str, PyEnum):
    """Status of a client communication."""
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    SENT = "sent"
    FAILED = "failed"


class CommunicationType(str, PyEnum):
    """Type of client communication."""
    NEW_REGULATION = "new_regulation"
    COMPLIANCE_UPDATE = "compliance_update"
    DEADLINE_REMINDER = "deadline_reminder"
    RESOLUTION_NOTICE = "resolution_notice"


class UserRole(str, PyEnum):
    """User roles in the platform."""
    INTERNAL_ADMIN = "internal_admin"
    INTERNAL_USER = "internal_user"
    CLIENT_ADMIN = "client_admin"
    CLIENT_USER = "client_user"


# ---- Models ----

class Tenant(Base):
    """Client organization (PCO customer)."""
    __tablename__ = "tenants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    descope_tenant_id = Column(String(255), unique=True, nullable=False, index=True)
    settings = Column(JSON, default=dict)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    subscriptions = relationship("Subscription", back_populates="tenant", cascade="all, delete-orphan")
    communications = relationship("Communication", back_populates="tenant")


class ComplianceRuleUrl(Base):
    """Admin-configured URL source for compliance rules."""
    __tablename__ = "compliance_rule_urls"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    url = Column(String(2000), nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    scrapes = relationship("ScrapedContent", back_populates="rule_url", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_comp_urls_active", "is_active"),
    )


class ScrapedContent(Base):
    """Raw text/HTML content scraped from a configured ComplianceRuleUrl."""
    __tablename__ = "scraped_content"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    url_id = Column(UUID(as_uuid=True), ForeignKey("compliance_rule_urls.id"), nullable=False)
    content_text = Column(Text, nullable=False)  # The extracted main body
    content_hash = Column(String(64), nullable=True)  # SHA-256 for diffing
    is_processed = Column(Boolean, default=False)  # Whether AI pipeline has read this yet
    chunks_processed = Column(Integer, default=0)  # Track progress for resumable chunked analysis
    total_chunks = Column(Integer, nullable=True)  # Total chunks for this content
    
    scraped_at = Column(DateTime, server_default=func.now(), nullable=False)

    # Relationships
    rule_url = relationship("ComplianceRuleUrl", back_populates="scrapes")

    __table_args__ = (
        Index("ix_scraped_content_url_id", "url_id"),
        Index("ix_scraped_content_processed", "is_processed"),
    )

    # Relationships
    gaps = relationship("ComplianceGap", back_populates="scraped_content", cascade="all, delete-orphan")


class ComplianceGap(Base):
    """An actionable compliance gap or requirement identified by the AI Engine."""
    __tablename__ = "compliance_gaps"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scraped_content_id = Column(UUID(as_uuid=True), ForeignKey("scraped_content.id", ondelete="CASCADE"), nullable=False)
    
    # AI Extracted Fields
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=False)
    status = Column(Enum(GapStatus, values_callable=lambda x: [e.value for e in x]), default=GapStatus.IDENTIFIED, nullable=False)
    severity = Column(Enum(GapSeverity, values_callable=lambda x: [e.value for e in x]), nullable=False)
    affected_modules = Column(JSON, nullable=True)  # List of PCO app modules affected
    deadline = Column(Date, nullable=True)
    
    is_new_requirement = Column(Boolean, default=False)
    
    # Audit trail
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    scraped_content = relationship("ScrapedContent", back_populates="gaps")

    __table_args__ = (
        Index("ix_comp_gaps_scraped", "scraped_content_id"),
        Index("ix_comp_gaps_status", "status"),
        Index("ix_comp_gaps_severity", "severity"),
    )


class Regulation(Base):
    """A tracked regulatory document or rule."""
    __tablename__ = "regulations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source = Column(String(100), nullable=False)  # e.g., "cms_gov", "federal_register"
    source_id = Column(String(500), nullable=True)  # External reference ID
    title = Column(String(1000), nullable=False)
    summary = Column(Text, nullable=True)
    raw_content = Column(Text, nullable=True)
    source_url = Column(String(2000), nullable=True)

    # AI Analysis
    ai_analysis = Column(JSON, default=dict)  # Structured AI analysis output
    relevance_score = Column(Float, nullable=True)  # AI-determined relevance matching PCO domains
    affected_areas = Column(JSON, default=list)  # List of affected EHR areas
    key_requirements = Column(JSON, default=list)  # Extracted requirements

    # Status & Timeline
    status = Column(Enum(RegulationStatus, values_callable=lambda x: [e.value for e in x]), default=RegulationStatus.PROPOSED, nullable=False)
    effective_date = Column(Date, nullable=True)
    comment_deadline = Column(Date, nullable=True)
    published_date = Column(Date, nullable=True)

    # Metadata
    cfr_references = Column(JSON, default=list)  # e.g., ["42 CFR 460"]
    agencies = Column(JSON, default=list)  # e.g., ["CMS", "HHS"]
    document_type = Column(String(100), nullable=True)  # "proposed_rule", "final_rule", "guidance"

    ingested_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    gap_analyses = relationship("GapAnalysis", back_populates="regulation", cascade="all, delete-orphan")
    communications = relationship("Communication", back_populates="regulation")

    __table_args__ = (
        Index("ix_regulations_source_source_id", "source", "source_id", unique=True),
        Index("ix_regulations_relevance", "relevance_score"),
        Index("ix_regulations_status", "status"),
        Index("ix_regulations_effective_date", "effective_date"),
    )


class GapAnalysis(Base):
    """A compliance gap identified between a regulation and the codebase."""
    __tablename__ = "gap_analyses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    regulation_id = Column(UUID(as_uuid=True), ForeignKey("regulations.id"), nullable=False)

    # Gap details
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    severity = Column(Enum(GapSeverity, values_callable=lambda x: [e.value for e in x]), nullable=False)
    status = Column(Enum(GapStatus, values_callable=lambda x: [e.value for e in x]), default=GapStatus.IDENTIFIED, nullable=False)
    
    # Optional references to where this gap originated
    affected_code = Column(JSON, default=list)  # [{repo, file_path, line_range, description}]
    affected_components = Column(JSON, default=list)  # ["enrollment", "billing", "care_plan"]

    # Work estimation
    assigned_team = Column(String(100), nullable=True)
    effort_hours = Column(Integer, nullable=True)
    effort_story_points = Column(Integer, nullable=True)

    # Jira integration
    jira_epic_key = Column(String(50), nullable=True)
    jira_epic_url = Column(String(500), nullable=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    regulation = relationship("Regulation", back_populates="gap_analyses")

    __table_args__ = (
        Index("ix_gaps_regulation", "regulation_id"),
        Index("ix_gaps_severity", "severity"),
        Index("ix_gaps_status", "status"),
        Index("ix_gaps_team", "assigned_team"),
    )


class Communication(Base):
    """A client-facing compliance communication."""
    __tablename__ = "communications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    regulation_id = Column(UUID(as_uuid=True), ForeignKey("regulations.id"), nullable=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=True)

    # Content
    type = Column(Enum(CommunicationType, values_callable=lambda x: [e.value for e in x]), nullable=False)
    subject = Column(String(500), nullable=False)
    content_html = Column(Text, nullable=False)
    content_plain = Column(Text, nullable=True)

    # Status
    status = Column(Enum(CommunicationStatus, values_callable=lambda x: [e.value for e in x]), default=CommunicationStatus.DRAFT, nullable=False)
    approved_by = Column(String(255), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    sent_at = Column(DateTime, nullable=True)
    recipient_count = Column(Integer, default=0)

    # Scheduling
    scheduled_send_at = Column(DateTime, nullable=True)
    reminder_interval_days = Column(Integer, nullable=True)
    next_reminder_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    regulation = relationship("Regulation", back_populates="communications")
    tenant = relationship("Tenant", back_populates="communications")

    __table_args__ = (
        Index("ix_comms_status", "status"),
        Index("ix_comms_tenant", "tenant_id"),
        Index("ix_comms_regulation", "regulation_id"),
    )


class ExecReport(Base):
    """Weekly executive summary report."""
    __tablename__ = "exec_reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    week_start = Column(Date, nullable=False)
    week_end = Column(Date, nullable=False)

    # Content
    summary_html = Column(Text, nullable=False)
    summary_plain = Column(Text, nullable=True)

    # Metrics
    metrics = Column(JSON, default=dict)  # {new_regulations, gaps_identified, gaps_resolved, ...}
    risks = Column(JSON, default=list)  # [{title, severity, description, mitigation}]
    highlights = Column(JSON, default=list)  # Key accomplishments

    # Delivery
    sent_to = Column(JSON, default=list)  # List of email addresses
    sent_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_reports_week", "week_start", unique=True),
    )


class Subscription(Base):
    """Client notification subscription preferences."""
    __tablename__ = "subscriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)

    feature = Column(String(100), nullable=False)  # "new_regulations", "gap_alerts", "deadline_reminders"
    is_active = Column(Boolean, default=True)
    notification_email = Column(String(500), nullable=True)  # Override email

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    tenant = relationship("Tenant", back_populates="subscriptions")

    __table_args__ = (
        Index("ix_subs_tenant_feature", "tenant_id", "feature", unique=True),
    )


class IntegrationConfig(Base):
    """Admin-configured integration credentials (GitLab, Jira, etc.)."""
    __tablename__ = "integration_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    integration_type = Column(String(50), nullable=False)  # "gitlab", "jira"
    config = Column(JSON, nullable=False)  # Encrypted config data
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_integrations_type", "integration_type"),
    )


class AuditLog(Base):
    """Audit trail for important actions."""
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(255), nullable=True)
    tenant_id = Column(UUID(as_uuid=True), nullable=True)
    action = Column(String(100), nullable=False)
    resource_type = Column(String(100), nullable=False)
    resource_id = Column(String(255), nullable=True)
    details = Column(JSON, default=dict)
    ip_address = Column(String(50), nullable=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_audit_user", "user_id"),
        Index("ix_audit_tenant", "tenant_id"),
        Index("ix_audit_action", "action"),
        Index("ix_audit_created", "created_at"),
    )


class PipelineLog(Base):
    """Internal log entries for the ingestion and analysis pipeline."""
    __tablename__ = "pipeline_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    component = Column(String(100), nullable=False)  # "scraper", "analysis", "ingestion"
    level = Column(String(20), nullable=False)  # "INFO", "WARNING", "ERROR"
    message = Column(Text, nullable=False)
    details = Column(JSON, nullable=True)  # Extra context (e.g., URL ID, doc ID)
    stack_trace = Column(Text, nullable=True)
    
    timestamp = Column(DateTime, server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_pipeline_logs_component", "component"),
        Index("ix_pipeline_logs_timestamp", "timestamp"),
        Index("ix_pipeline_logs_level", "level"),
    )
