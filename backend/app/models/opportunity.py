"""Opportunity models for storing opportunities and user feeds."""
from sqlalchemy import Column, String, Text, Integer, Float, Date, Boolean, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.base import BaseModel


class OpportunityCatalog(Base, BaseModel):
    """
    Catalog of available opportunities (grants, conferences, fellowships, etc.).
    
    This is the master catalog of opportunities. Each opportunity can be
    recommended to multiple users.
    
    Attributes:
        opportunity_id: Unique external identifier (e.g., "nsf_grfp_2026")
        title: Opportunity title
        opportunity_type: Type (grant, conference, fellowship, etc.)
        disciplines: List of target disciplines
        eligible_stages: List of eligible research stages
        deadline: Application deadline
        description: Full description
        keywords: Search/matching keywords
        funding_amount: Funding amount (if applicable)
        prestige_level: "high", "medium", "low"
        geographic_scope: "us", "eu", "global", etc.
        source_url: Official URL
        organization: Offering organization
        is_active: Whether opportunity is currently active
        requires_subscription: Premium feature flag
        subscription_tier: Required subscription tier (if gated)
    """
    
    __tablename__ = "opportunities_catalog"
    
    opportunity_id = Column(String(255), unique=True, nullable=False, index=True)
    title = Column(String, nullable=False)
    opportunity_type = Column(String(50), nullable=False, index=True)
    
    # Target audience
    disciplines = Column(ARRAY(String), nullable=False)
    eligible_stages = Column(ARRAY(String), nullable=False)
    
    # Timing
    deadline = Column(Date, nullable=False, index=True)
    
    # Content
    description = Column(Text, nullable=True)
    keywords = Column(ARRAY(String), nullable=True)
    
    # Details
    funding_amount = Column(Float, nullable=True)
    prestige_level = Column(String(20), nullable=True)
    geographic_scope = Column(String(50), nullable=True)
    
    # Source
    source_url = Column(String, nullable=True)
    organization = Column(String, nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    
    # Subscription gating
    requires_subscription = Column(Boolean, default=False, nullable=False)
    subscription_tier = Column(String(50), nullable=True)  # "premium", "pro", etc.
    
    # Relationships
    feed_items = relationship("OpportunityFeedItem", back_populates="opportunity")
    user_opportunities = relationship(
        "UserOpportunity",
        back_populates="opportunity",
        cascade="all, delete-orphan",
    )
    
    # Indexes
    __table_args__ = (
        Index("idx_opportunities_deadline_active", "deadline", "is_active"),
        Index("idx_opportunities_type_active", "opportunity_type", "is_active"),
    )


class OpportunityFeedSnapshot(Base, BaseModel):
    """
    Snapshot of a user's personalized opportunity feed.
    
    Generated periodically (e.g., daily, weekly) or on-demand.
    Contains ranked opportunities relevant to the user.
    
    Attributes:
        user_id: User this feed belongs to
        snapshot_date: When this snapshot was generated
        user_profile_snapshot: User profile at time of generation
        timeline_context_snapshot: Timeline context at time of generation
        total_opportunities_scored: Total opportunities considered
        feed_type: "daily", "weekly", "on_demand"
        subscription_tier: User's subscription tier at generation time
    """
    
    __tablename__ = "opportunity_feed_snapshots"
    
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    snapshot_date = Column(Date, nullable=False, index=True)
    
    # Snapshot data (for reproducibility)
    user_profile_snapshot = Column(JSONB, nullable=False)
    timeline_context_snapshot = Column(JSONB, nullable=True)
    
    # Metadata
    total_opportunities_scored = Column(Integer, nullable=False)
    feed_type = Column(String(50), nullable=False)  # "daily", "weekly", "on_demand"
    subscription_tier = Column(String(50), nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="opportunity_feeds")
    feed_items = relationship(
        "OpportunityFeedItem",
        back_populates="feed_snapshot",
        cascade="all, delete-orphan"
    )
    
    # Indexes
    __table_args__ = (
        Index("idx_feed_snapshots_user_date", "user_id", "snapshot_date"),
    )


class OpportunityFeedItem(Base, BaseModel):
    """
    Individual item in a user's opportunity feed.
    
    Links a feed snapshot to an opportunity with relevance score.
    
    Attributes:
        feed_snapshot_id: Parent feed snapshot
        opportunity_id: Opportunity in catalog
        rank: Rank in feed (1 = top)
        overall_score: Overall relevance score
        discipline_score: Discipline alignment score
        stage_score: Stage appropriateness score
        timeline_score: Timeline compatibility score
        deadline_score: Deadline suitability score
        reason_tags: List of reason tags
        explanation: Human-readable explanation
        urgency_level: "high", "medium", "low"
        recommended_action: "apply_now", "prepare", "monitor", "skip"
        user_dismissed: Whether user dismissed this item
        user_saved: Whether user saved this item
        user_applied: Whether user applied
    """
    
    __tablename__ = "opportunity_feed_items"
    
    feed_snapshot_id = Column(
        UUID(as_uuid=True),
        ForeignKey("opportunity_feed_snapshots.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    opportunity_id = Column(
        UUID(as_uuid=True),
        ForeignKey("opportunities_catalog.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Ranking
    rank = Column(Integer, nullable=False)
    
    # Scores
    overall_score = Column(Float, nullable=False)
    discipline_score = Column(Float, nullable=False)
    stage_score = Column(Float, nullable=False)
    timeline_score = Column(Float, nullable=False)
    deadline_score = Column(Float, nullable=False)
    
    # Reasoning
    reason_tags = Column(ARRAY(String), nullable=False)
    explanation = Column(Text, nullable=False)
    urgency_level = Column(String(20), nullable=False)
    recommended_action = Column(String(50), nullable=False)
    
    # User interactions
    user_dismissed = Column(Boolean, default=False, nullable=False)
    user_saved = Column(Boolean, default=False, nullable=False)
    user_applied = Column(Boolean, default=False, nullable=False)
    
    # Relationships
    feed_snapshot = relationship("OpportunityFeedSnapshot", back_populates="feed_items")
    opportunity = relationship("OpportunityCatalog", back_populates="feed_items")
    
    # Indexes
    __table_args__ = (
        Index("idx_feed_items_snapshot_rank", "feed_snapshot_id", "rank"),
        Index("idx_feed_items_user_actions", "user_saved", "user_applied"),
    )
