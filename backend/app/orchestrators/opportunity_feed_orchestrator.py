"""
OpportunityFeedOrchestrator - Generate personalized opportunity feeds.

Steps:
1. Load opportunities from catalog
2. Score relevance using OpportunityRelevanceEngine
3. Rank opportunities
4. Store snapshot per user
5. Respect subscription gating
"""

from typing import Dict, List, Optional, Any
from uuid import UUID
from datetime import date
from sqlalchemy.orm import Session

from app.orchestrators.base import BaseOrchestrator
from app.models.user import User
from app.models.opportunity import (
    OpportunityCatalog,
    OpportunityFeedSnapshot,
    OpportunityFeedItem,
)
from app.models.committed_timeline import CommittedTimeline
from app.services.opportunity_relevance_engine import (
    OpportunityRelevanceEngine,
    Opportunity,
    UserProfile,
    TimelineContext,
    ResearchStage,
    OpportunityType,
)
from app.data.opportunities_catalog import get_active_opportunities
from app.core.event_taxonomy import EventType
from app.services.event_store import emit_event


class OpportunityFeedOrchestratorError(Exception):
    """Base exception for opportunity feed orchestrator errors."""
    pass


class InsufficientSubscriptionError(OpportunityFeedOrchestratorError):
    """Raised when user tries to access premium opportunities without subscription."""
    pass


class OpportunityFeedOrchestrator(BaseOrchestrator[Dict[str, Any]]):
    """
    Orchestrator for generating personalized opportunity feeds.
    
    Extends BaseOrchestrator to provide:
    - Idempotent feed generation
    - Decision tracing
    - Evidence bundling
    
    Coordinates:
    - Opportunity catalog loading
    - Relevance scoring
    - Ranking
    - Snapshot storage
    - Subscription gating
    """
    
    @property
    def orchestrator_name(self) -> str:
        """Return orchestrator name."""
        return "opportunity_feed_orchestrator"
    
    def __init__(self, db: Session, user_id: Optional[UUID] = None):
        """
        Initialize opportunity feed orchestrator.
        
        Args:
            db: Database session
            user_id: Optional user ID
        """
        super().__init__(db, user_id)
        self.relevance_engine = OpportunityRelevanceEngine()
    
    def generate_feed(
        self,
        request_id: str,
        user_id: UUID,
        feed_type: str = "on_demand",
        min_score: float = 50.0,
        limit: Optional[int] = None,
        include_premium: bool = False
    ) -> Dict[str, Any]:
        """
        Generate personalized opportunity feed for user.
        
        Steps:
        1. Load user profile and timeline context
        2. Load opportunities from catalog
        3. Filter by subscription tier
        4. Score and rank opportunities
        5. Store feed snapshot
        6. Return feed summary
        
        Args:
            request_id: Idempotency key
            user_id: User ID
            feed_type: "daily", "weekly", "on_demand"
            min_score: Minimum relevance score (0-100)
            limit: Maximum number of opportunities to return
            include_premium: Whether to include premium opportunities
            
        Returns:
            Feed summary with top opportunities
            
        Raises:
            OpportunityFeedOrchestratorError: If user not found
        """
        return self.execute(
            request_id=request_id,
            input_data={
                "user_id": str(user_id),
                "feed_type": feed_type,
                "min_score": min_score,
                "limit": limit,
                "include_premium": include_premium
            }
        )
    
    def _execute_pipeline(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the feed generation pipeline.
        
        Args:
            context: Execution context with input data
            
        Returns:
            Feed summary
        """
        user_id = UUID(context["user_id"])
        feed_type = context.get("feed_type", "on_demand")
        min_score = context.get("min_score", 50.0)
        limit = context.get("limit")
        include_premium = context.get("include_premium", False)
        
        # Step 1: Load user profile and timeline
        with self._trace_step("load_user_context") as step:
            user_profile, timeline_context = self._load_user_context(user_id)
            step.details = {
                "user_id": str(user_id),
                "discipline": user_profile.discipline,
                "research_stage": user_profile.research_stage.value,
                "has_timeline": timeline_context is not None
            }
            self.add_evidence(
                evidence_type="user_profile",
                data={
                    "discipline": user_profile.discipline,
                    "subdisciplines": user_profile.subdisciplines,
                    "stage": user_profile.research_stage.value,
                    "keywords": user_profile.keywords
                },
                source=f"User:{user_id}",
                confidence=1.0
            )
        
        # Step 2: Load opportunities from catalog
        with self._trace_step("load_opportunities_catalog") as step:
            opportunities = self._load_opportunities_catalog()
            step.details = {
                "total_opportunities": len(opportunities),
                "active_opportunities": len([o for o in opportunities if o.deadline >= date.today()])
            }
            self.add_evidence(
                evidence_type="catalog_loaded",
                data={"opportunity_count": len(opportunities)},
                source="OpportunitiesCatalog",
                confidence=1.0
            )
        
        # Step 3: Filter by subscription tier
        with self._trace_step("apply_subscription_filter") as step:
            user = self.db.query(User).filter(User.id == user_id).first()
            filtered_opportunities = self._filter_by_subscription(
                opportunities,
                user,
                include_premium
            )
            step.details = {
                "before_filter": len(opportunities),
                "after_filter": len(filtered_opportunities),
                "filtered_out": len(opportunities) - len(filtered_opportunities),
                "user_subscription_tier": getattr(user, "subscription_tier", None)
            }
            self.add_evidence(
                evidence_type="subscription_filter",
                data={
                    "include_premium": include_premium,
                    "filtered_count": len(filtered_opportunities)
                },
                source="SubscriptionGate",
                confidence=1.0
            )
        
        # Step 4: Score and rank opportunities
        with self._trace_step("score_and_rank") as step:
            ranked_scores = self.relevance_engine.rank_opportunities(
                opportunities=filtered_opportunities,
                user_profile=user_profile,
                timeline_context=timeline_context,
                min_score=min_score
            )
            step.details = {
                "scored_count": len(ranked_scores),
                "average_score": sum(s.overall_score for s in ranked_scores) / len(ranked_scores) if ranked_scores else 0,
                "top_score": ranked_scores[0].overall_score if ranked_scores else 0,
                "apply_now_count": len([s for s in ranked_scores if s.recommended_action == "apply_now"])
            }
            self.add_evidence(
                evidence_type="relevance_scores",
                data={
                    "scored_count": len(ranked_scores),
                    "top_5_scores": [s.overall_score for s in ranked_scores[:5]]
                },
                source="OpportunityRelevanceEngine",
                confidence=1.0
            )
        
        # Step 5: Apply limit
        if limit:
            with self._trace_step("apply_limit") as step:
                ranked_scores = ranked_scores[:limit]
                step.details = {"limit": limit, "final_count": len(ranked_scores)}
        
        # Step 6: Store feed snapshot
        with self._trace_step("store_feed_snapshot") as step:
            snapshot_id = self._store_feed_snapshot(
                user_id=user_id,
                user_profile=user_profile,
                timeline_context=timeline_context,
                ranked_scores=ranked_scores,
                feed_type=feed_type,
                total_scored=len(ranked_scores)
            )
            step.details = {
                "snapshot_id": str(snapshot_id),
                "feed_items_count": len(ranked_scores)
            }
            self.add_evidence(
                evidence_type="feed_snapshot",
                data={"snapshot_id": str(snapshot_id)},
                source=f"OpportunityFeedSnapshot:{snapshot_id}",
                confidence=1.0
            )
        
        # Step 7: Generate summary
        with self._trace_step("generate_summary") as step:
            summary = self._generate_feed_summary(
                snapshot_id=snapshot_id,
                ranked_scores=ranked_scores,
                user_profile=user_profile
            )
            step.details = {
                "top_opportunities": len(ranked_scores[:5]),
                "high_urgency_count": len([s for s in ranked_scores if s.urgency_level == "high"])
            }
        
        return summary
    
    def _load_user_context(
        self,
        user_id: UUID
    ) -> tuple[UserProfile, Optional[TimelineContext]]:
        """
        Load user profile and timeline context.
        
        Args:
            user_id: User ID
            
        Returns:
            Tuple of (UserProfile, TimelineContext)
            
        Raises:
            OpportunityFeedOrchestratorError: If user not found
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise OpportunityFeedOrchestratorError(f"User {user_id} not found")
        
        # Create user profile
        # For demo, use simple mapping. In production, this would use richer data
        discipline = user.field_of_study or "Computer Science"
        
        # Determine research stage (simplified)
        # In production, this would be derived from user's timeline or profile data
        stage = ResearchStage.EARLY  # Default
        
        # Check if user has a committed timeline to better determine stage
        timeline = self.db.query(CommittedTimeline).filter(
            CommittedTimeline.user_id == user_id
        ).order_by(CommittedTimeline.created_at.desc()).first()
        
        timeline_context = None
        if timeline:
            # Extract timeline context
            # In production, this would be more sophisticated
            timeline_context = self._extract_timeline_context(timeline)
            
            # Determine stage from timeline progress
            # Simplified logic
            if timeline.overall_progress_percentage:
                if timeline.overall_progress_percentage < 30:
                    stage = ResearchStage.EARLY
                elif timeline.overall_progress_percentage < 70:
                    stage = ResearchStage.MID
                else:
                    stage = ResearchStage.LATE
        
        user_profile = UserProfile(
            discipline=discipline,
            subdisciplines=[],  # Could extract from user data
            research_stage=stage,
            keywords=[],  # Could extract from user's documents/research
            institution_type=getattr(user, "institution_type", None),
            geographic_region="US"  # Default
        )
        
        return user_profile, timeline_context
    
    def _extract_timeline_context(
        self,
        timeline: CommittedTimeline
    ) -> Optional[TimelineContext]:
        """Extract timeline context from committed timeline."""
        # Get stages and milestones
        stages = self.db.query(
            from app.models.timeline_stage import TimelineStage
        ).filter(
            TimelineStage.committed_timeline_id == timeline.id
        ).order_by(TimelineStage.order_index).all()
        
        if not stages:
            return None
        
        # Find current stage (first incomplete stage)
        current_stage = next(
            (s for s in stages if s.status != "completed"),
            stages[-1]  # Default to last stage
        )
        
        # Get upcoming stages
        current_idx = stages.index(current_stage)
        upcoming_stages = [
            s.stage_name
            for s in stages[current_idx + 1:current_idx + 3]
        ]
        
        # Get critical milestones (from current and next stage)
        from app.models.timeline_milestone import TimelineMilestone
        upcoming_milestones = self.db.query(TimelineMilestone).filter(
            TimelineMilestone.stage_id.in_([
                s.id for s in stages[current_idx:current_idx + 2]
            ]),
            TimelineMilestone.is_completed == False
        ).limit(3).all()
        
        return TimelineContext(
            current_stage_name=current_stage.stage_name,
            current_stage_progress=current_stage.progress_percentage / 100 if current_stage.progress_percentage else 0.0,
            upcoming_stages=upcoming_stages,
            critical_milestones=[m.milestone_name for m in upcoming_milestones],
            expected_completion_date=timeline.expected_completion_date
        )
    
    def _load_opportunities_catalog(self) -> List[Opportunity]:
        """
        Load opportunities from catalog.
        
        Returns:
            List of Opportunity objects
        """
        # Load from static catalog
        catalog_data = get_active_opportunities()
        
        opportunities = []
        for opp_data in catalog_data:
            # Convert to Opportunity object
            opportunity = Opportunity(
                opportunity_id=opp_data["opportunity_id"],
                title=opp_data["title"],
                opportunity_type=OpportunityType(opp_data["opportunity_type"]),
                disciplines=opp_data["disciplines"],
                eligible_stages=[
                    ResearchStage(stage) for stage in opp_data["eligible_stages"]
                ],
                deadline=opp_data["deadline"],
                description=opp_data.get("description"),
                keywords=opp_data.get("keywords", []),
                funding_amount=opp_data.get("funding_amount"),
                prestige_level=opp_data.get("prestige_level"),
                geographic_scope=opp_data.get("geographic_scope")
            )
            opportunities.append(opportunity)
        
        return opportunities
    
    def _filter_by_subscription(
        self,
        opportunities: List[Opportunity],
        user: User,
        include_premium: bool
    ) -> List[Opportunity]:
        """
        Filter opportunities by subscription tier.
        
        Args:
            opportunities: List of opportunities
            user: User object
            include_premium: Whether to include premium opportunities
            
        Returns:
            Filtered list of opportunities
        """
        # Load full catalog data to check subscription requirements
        catalog_data = get_active_opportunities()
        catalog_map = {opp["opportunity_id"]: opp for opp in catalog_data}
        
        filtered = []
        for opp in opportunities:
            catalog_entry = catalog_map.get(opp.opportunity_id)
            if not catalog_entry:
                continue
            
            # Check if requires subscription
            if catalog_entry.get("requires_subscription", False):
                # Only include if user has appropriate subscription and include_premium is True
                if include_premium:
                    # In production, verify user.subscription_tier matches required tier
                    user_tier = getattr(user, "subscription_tier", None)
                    required_tier = catalog_entry.get("subscription_tier")
                    
                    # For demo, allow if user has any subscription_tier attribute
                    if user_tier:
                        filtered.append(opp)
                    # Otherwise, skip premium opportunity
                # If include_premium is False, skip
            else:
                # Free opportunity, always include
                filtered.append(opp)
        
        return filtered
    
    def _store_feed_snapshot(
        self,
        user_id: UUID,
        user_profile: UserProfile,
        timeline_context: Optional[TimelineContext],
        ranked_scores: List[Any],
        feed_type: str,
        total_scored: int
    ) -> UUID:
        """
        Store feed snapshot and items in database.
        
        Args:
            user_id: User ID
            user_profile: User profile snapshot
            timeline_context: Timeline context snapshot
            ranked_scores: Ranked relevance scores
            feed_type: Feed type
            total_scored: Total opportunities scored
            
        Returns:
            UUID of created feed snapshot
        """
        # Create feed snapshot
        snapshot = OpportunityFeedSnapshot(
            user_id=user_id,
            snapshot_date=date.today(),
            user_profile_snapshot={
                "discipline": user_profile.discipline,
                "subdisciplines": user_profile.subdisciplines,
                "research_stage": user_profile.research_stage.value,
                "keywords": user_profile.keywords
            },
            timeline_context_snapshot={
                "current_stage_name": timeline_context.current_stage_name,
                "current_stage_progress": timeline_context.current_stage_progress,
                "upcoming_stages": timeline_context.upcoming_stages,
                "critical_milestones": timeline_context.critical_milestones
            } if timeline_context else None,
            total_opportunities_scored=total_scored,
            feed_type=feed_type,
            subscription_tier=None  # Would get from user in production
        )
        
        self.db.add(snapshot)
        self.db.flush()
        user = self.db.query(User).filter(User.id == user_id).first()
        emit_event(
            self.db,
            user_id=user_id,
            role=getattr(user, "role", "researcher"),
            event_type=EventType.OPPORTUNITY_SAVED.value,
            source_module="opportunity_feed",
            entity_type="opportunity_feed_snapshot",
            entity_id=snapshot.id,
            metadata={"feed_type": feed_type, "total_scored": total_scored},
        )
        # Store feed items
        # First, get or create opportunity catalog entries
        catalog_data = get_active_opportunities()
        catalog_map = {opp["opportunity_id"]: opp for opp in catalog_data}
        
        for rank, score in enumerate(ranked_scores, 1):
            # Get or create catalog entry
            catalog_entry_data = catalog_map.get(score.opportunity_id)
            if not catalog_entry_data:
                continue
            
            catalog_entry = self.db.query(OpportunityCatalog).filter(
                OpportunityCatalog.opportunity_id == score.opportunity_id
            ).first()
            
            if not catalog_entry:
                # Create catalog entry
                catalog_entry = OpportunityCatalog(
                    opportunity_id=catalog_entry_data["opportunity_id"],
                    title=catalog_entry_data["title"],
                    opportunity_type=catalog_entry_data["opportunity_type"],
                    disciplines=catalog_entry_data["disciplines"],
                    eligible_stages=catalog_entry_data["eligible_stages"],
                    deadline=catalog_entry_data["deadline"],
                    description=catalog_entry_data.get("description"),
                    keywords=catalog_entry_data.get("keywords", []),
                    funding_amount=catalog_entry_data.get("funding_amount"),
                    prestige_level=catalog_entry_data.get("prestige_level"),
                    geographic_scope=catalog_entry_data.get("geographic_scope"),
                    source_url=catalog_entry_data.get("source_url"),
                    organization=catalog_entry_data.get("organization"),
                    is_active=True,
                    requires_subscription=catalog_entry_data.get("requires_subscription", False),
                    subscription_tier=catalog_entry_data.get("subscription_tier")
                )
                self.db.add(catalog_entry)
                self.db.flush()
            
            # Create feed item
            feed_item = OpportunityFeedItem(
                feed_snapshot_id=snapshot.id,
                opportunity_id=catalog_entry.id,
                rank=rank,
                overall_score=score.overall_score,
                discipline_score=score.discipline_score,
                stage_score=score.stage_score,
                timeline_score=score.timeline_score,
                deadline_score=score.deadline_score,
                reason_tags=[tag.value for tag in score.reason_tags],
                explanation=score.explanation,
                urgency_level=score.urgency_level,
                recommended_action=score.recommended_action
            )
            self.db.add(feed_item)
        
        self.db.commit()
        self.db.refresh(snapshot)
        
        return snapshot.id
    
    def _generate_feed_summary(
        self,
        snapshot_id: UUID,
        ranked_scores: List[Any],
        user_profile: UserProfile
    ) -> Dict[str, Any]:
        """
        Generate feed summary for response.
        
        Args:
            snapshot_id: Feed snapshot ID
            ranked_scores: Ranked relevance scores
            user_profile: User profile
            
        Returns:
            Feed summary dictionary
        """
        # Group by recommended action
        apply_now = [s for s in ranked_scores if s.recommended_action == "apply_now"]
        prepare = [s for s in ranked_scores if s.recommended_action == "prepare"]
        monitor = [s for s in ranked_scores if s.recommended_action == "monitor"]
        
        # Group by urgency
        high_urgency = [s for s in ranked_scores if s.urgency_level == "high"]
        
        return {
            "snapshot_id": str(snapshot_id),
            "snapshot_date": date.today().isoformat(),
            "user_profile": {
                "discipline": user_profile.discipline,
                "research_stage": user_profile.research_stage.value
            },
            "summary": {
                "total_opportunities": len(ranked_scores),
                "apply_now_count": len(apply_now),
                "prepare_count": len(prepare),
                "monitor_count": len(monitor),
                "high_urgency_count": len(high_urgency),
                "average_score": sum(s.overall_score for s in ranked_scores) / len(ranked_scores) if ranked_scores else 0
            },
            "top_opportunities": [
                {
                    "opportunity_id": s.opportunity_id,
                    "rank": i + 1,
                    "overall_score": s.overall_score,
                    "recommended_action": s.recommended_action,
                    "urgency_level": s.urgency_level,
                    "explanation": s.explanation,
                    "reason_tags": [tag.value for tag in s.reason_tags]
                }
                for i, s in enumerate(ranked_scores[:10])
            ],
            "apply_now": [
                {
                    "opportunity_id": s.opportunity_id,
                    "overall_score": s.overall_score,
                    "explanation": s.explanation
                }
                for s in apply_now[:5]
            ],
            "high_urgency": [
                {
                    "opportunity_id": s.opportunity_id,
                    "overall_score": s.overall_score,
                    "urgency_level": s.urgency_level
                }
                for s in high_urgency[:5]
            ]
        }
