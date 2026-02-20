"""Analytics engine for aggregating timeline progress and journey health data."""
import logging
from typing import Dict, List, Optional, Any
from uuid import UUID
from datetime import date, timedelta
from dataclasses import dataclass, field
from sqlalchemy.orm import Session

from app.models.journey_assessment import JourneyAssessment
from app.models.progress_event import ProgressEvent
from app.models.committed_timeline import CommittedTimeline
from app.models.timeline_stage import TimelineStage
from app.models.timeline_milestone import TimelineMilestone
from app.models.analytics_snapshot import AnalyticsSnapshot
from app.services.progress_service import ProgressService
from app.services.risk_fusion_engine import RiskFusionEngine
from app.services.temporal_engine import TemporalEngine


@dataclass
class TimeSeriesPoint:
    """A single point in a time series."""
    date: date
    value: float
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class TimeSeriesSummary:
    """Summary of a time series."""
    metric_name: str
    points: List[TimeSeriesPoint]
    current_value: Optional[float]
    trend: Optional[str]  # "increasing", "decreasing", "stable", None
    average: Optional[float]
    min_value: Optional[float]
    max_value: Optional[float]


@dataclass
class StatusIndicator:
    """Status indicator for a metric."""
    name: str
    value: Any
    status: str  # "excellent", "good", "fair", "concerning", "critical", "unknown"
    message: Optional[str] = None


@dataclass
class AnalyticsReport:
    """Complete analytics report."""
    user_id: UUID
    timeline_id: Optional[UUID]
    generated_at: date
    time_series: List[TimeSeriesSummary]
    status_indicators: List[StatusIndicator]
    summary: Dict[str, Any]


@dataclass
class AnalyticsSummary:
    """Structured analytics summary for dashboard."""
    timeline_id: UUID
    user_id: UUID
    generated_at: date

    # Timeline status
    timeline_status: str  # "on_track" | "delayed" | "completed"

    # Milestone metrics
    milestone_completion_percentage: float
    total_milestones: int
    completed_milestones: int
    pending_milestones: int

    # Delay metrics
    total_delays: int
    overdue_milestones: int
    overdue_critical_milestones: int
    average_delay_days: float
    max_delay_days: int

    # Journey health (from latest assessment)
    latest_health_score: Optional[float]  # 0-100
    health_dimensions: Dict[str, float]  # dimension_name -> score (0-100)

    # Longitudinal summary
    longitudinal_summary: Dict[str, Any]

    # Temporal analysis (from TemporalEngine)
    temporal_analysis: Optional[Dict[str, Any]] = field(default=None)


class AnalyticsEngine:
    """
    Analytics engine for aggregating timeline progress and journey health.
    
    Rules:
    - No predictions: Only aggregates historical data
    - Time-series summaries: Aggregates data points over time
    - Status indicators: Computes current status from historical data
    - Deterministic: Same inputs produce same outputs
    
    Inputs:
    - Timeline progress (from ProgressService)
    - Journey health (from JourneyAssessment)
    - (Future) Writing intelligence
    
    Outputs:
    - Time-series summaries
    - Status indicators
    """
    
    def __init__(self, db: Session, include_temporal: bool = False, use_llm: bool = True):
        """
        Initialize analytics engine.

        Args:
            db: Database session
            include_temporal: Whether to include temporal analysis
            use_llm: Whether to use LLM for temporal summary generation
        """
        self.db = db
        self.progress_service = ProgressService(db)
        self.include_temporal = include_temporal
        self.use_llm = use_llm
        self._temporal_engine: Optional[TemporalEngine] = None

    @property
    def temporal_engine(self) -> TemporalEngine:
        """Lazy initialization of temporal engine."""
        if self._temporal_engine is None:
            self._temporal_engine = TemporalEngine(use_llm=self.use_llm)
        return self._temporal_engine
    
    def aggregate(
        self,
        committed_timeline: CommittedTimeline,
        progress_events: List[ProgressEvent],
        latest_assessment: Optional[JourneyAssessment] = None,
    ) -> AnalyticsSummary:
        """
        Aggregate timeline progress and journey health data.
        
        Rules:
        - Deterministic only: Same inputs produce same outputs
        - No predictions: Only aggregates historical data
        - No ML: Pure mathematical calculations
        
        Logic:
        1. Compute overall timeline status (on_track | delayed | completed)
        2. Aggregate milestone completion percentage
        3. Aggregate delay counts and overdue milestones
        4. Aggregate journey health dimensions (from latest assessment)
        5. Generate longitudinal summary object
        
        Args:
            committed_timeline: CommittedTimeline object
            progress_events: List of ProgressEvent objects
            latest_assessment: Optional latest JourneyAssessment
            
        Returns:
            AnalyticsSummary with aggregated metrics
        """
        # Get all milestones for this timeline
        stages = self.db.query(TimelineStage).filter(
            TimelineStage.committed_timeline_id == committed_timeline.id
        ).all()
        
        milestones = []
        for stage in stages:
            stage_milestones = self.db.query(TimelineMilestone).filter(
                TimelineMilestone.timeline_stage_id == stage.id
            ).all()
            milestones.extend(stage_milestones)
        
        # Step 1: Compute overall timeline status
        timeline_status = self._compute_timeline_status(
            committed_timeline=committed_timeline,
            milestones=milestones,
            progress_events=progress_events
        )
        
        # Step 2: Aggregate milestone completion percentage
        completion_metrics = self._aggregate_milestone_completion(milestones)
        
        # Step 3: Aggregate delay counts and overdue milestones
        delay_metrics = self._aggregate_delay_metrics(
            milestones=milestones,
            progress_events=progress_events
        )
        
        # Step 4: Aggregate journey health dimensions
        health_metrics = self._aggregate_health_dimensions(latest_assessment)
        
        # Step 5: Generate longitudinal summary
        longitudinal_summary = self._generate_longitudinal_summary(
            committed_timeline=committed_timeline,
            milestones=milestones,
            progress_events=progress_events,
            latest_assessment=latest_assessment
        )

        # Step 6: Generate temporal analysis if enabled
        temporal_analysis = None
        if self.include_temporal:
            try:
                temporal_analysis = self._generate_temporal_analysis(
                    user_id=committed_timeline.user_id,
                    committed_timeline=committed_timeline,
                    progress_events=progress_events,
                    milestones=milestones,
                    longitudinal_summary=longitudinal_summary,
                )
            except Exception as e:
                logger.error(f"Failed to generate temporal analysis: {e}")
                temporal_analysis = None

        return AnalyticsSummary(
            timeline_id=committed_timeline.id,
            user_id=committed_timeline.user_id,
            generated_at=date.today(),
            timeline_status=timeline_status,
            milestone_completion_percentage=completion_metrics["completion_percentage"],
            total_milestones=completion_metrics["total"],
            completed_milestones=completion_metrics["completed"],
            pending_milestones=completion_metrics["pending"],
            total_delays=delay_metrics["total_delays"],
            overdue_milestones=delay_metrics["overdue_count"],
            overdue_critical_milestones=delay_metrics["overdue_critical_count"],
            average_delay_days=delay_metrics["average_delay"],
            max_delay_days=delay_metrics["max_delay"],
            latest_health_score=health_metrics["overall_score"],
            health_dimensions=health_metrics["dimensions"],
            longitudinal_summary=longitudinal_summary,
            temporal_analysis=temporal_analysis,
        )
    
    def _aggregate_timeline_progress(
        self,
        user_id: UUID,
        timeline_id: Optional[UUID],
        start_date: date,
        end_date: date
    ) -> List[TimeSeriesSummary]:
        """
        Aggregate timeline progress into time-series.
        
        Returns time-series for:
        - Completion percentage over time
        - Milestone completion rate
        - Delay trends
        
        Args:
            user_id: User ID
            timeline_id: Optional timeline ID
            start_date: Start date
            end_date: End date
            
        Returns:
            List of TimeSeriesSummary objects
        """
        series = []
        
        # Get committed timeline
        if timeline_id:
            timeline = self.db.query(CommittedTimeline).filter(
                CommittedTimeline.id == timeline_id,
                CommittedTimeline.user_id == user_id
            ).first()
        else:
            # Get most recent committed timeline
            timeline = self.db.query(CommittedTimeline).filter(
                CommittedTimeline.user_id == user_id
            ).order_by(CommittedTimeline.committed_date.desc()).first()
        
        if not timeline:
            return series
        
        # Get milestones for this timeline via stages
        stages = self.db.query(TimelineStage).filter(
            TimelineStage.committed_timeline_id == timeline.id
        ).all()
        
        milestones = []
        for stage in stages:
            stage_milestones = self.db.query(TimelineMilestone).filter(
                TimelineMilestone.timeline_stage_id == stage.id
            ).all()
            milestones.extend(stage_milestones)
        
        if not milestones:
            return series
        
        # Get progress events
        milestone_ids = [m.id for m in milestones]
        events = self.db.query(ProgressEvent).filter(
            ProgressEvent.user_id == user_id,
            ProgressEvent.milestone_id.in_(milestone_ids),
            ProgressEvent.event_date >= start_date,
            ProgressEvent.event_date <= end_date
        ).order_by(ProgressEvent.event_date.asc()).all()
        
        # Build completion percentage time-series
        completion_points = []
        total_milestones = len(milestones)
        completed_count = 0
        
        # Initialize with start date
        if timeline.committed_date and timeline.committed_date >= start_date:
            completion_points.append(TimeSeriesPoint(
                date=timeline.committed_date,
                value=0.0,
                metadata={"total": total_milestones, "completed": 0}
            ))
        
        # Process events chronologically
        for event in events:
            if event.event_type == "milestone_completed":
                completed_count += 1
                completion_pct = (completed_count / total_milestones) * 100 if total_milestones > 0 else 0.0
                completion_points.append(TimeSeriesPoint(
                    date=event.event_date,
                    value=completion_pct,
                    metadata={
                        "total": total_milestones,
                        "completed": completed_count,
                        "event_id": str(event.id)
                    }
                ))
        
        # Add current state
        current_progress = self.progress_service.get_timeline_progress(timeline.id)
        if current_progress and current_progress.get("has_data"):
            current_completion = current_progress.get("completion_percentage", 0.0)
            if not completion_points or completion_points[-1].date < end_date:
                completion_points.append(TimeSeriesPoint(
                    date=end_date,
                    value=current_completion,
                    metadata={
                        "total": current_progress.get("total_milestones", total_milestones),
                        "completed": current_progress.get("completed_milestones", completed_count)
                    }
                ))
        
        if completion_points:
            series.append(self._create_time_series_summary(
                metric_name="timeline_completion_percentage",
                points=completion_points
            ))
        
        # Build delay trend time-series
        delay_points = []
        for event in events:
            if event.milestone_id:
                milestone = next((m for m in milestones if m.id == event.milestone_id), None)
                if milestone and milestone.target_date:
                    if event.event_type == "milestone_completed" and milestone.actual_completion_date:
                        delay_days = (milestone.actual_completion_date - milestone.target_date).days
                        delay_points.append(TimeSeriesPoint(
                            date=event.event_date,
                            value=float(delay_days),
                            metadata={
                                "milestone_id": str(milestone.id),
                                "milestone_title": milestone.title,
                                "is_critical": milestone.is_critical
                            }
                        ))
        
        if delay_points:
            series.append(self._create_time_series_summary(
                metric_name="milestone_delay_days",
                points=delay_points
            ))
        
        return series
    
    def _aggregate_journey_health(
        self,
        user_id: UUID,
        start_date: date,
        end_date: date
    ) -> List[TimeSeriesSummary]:
        """
        Aggregate journey health assessments into time-series.
        
        Returns time-series for:
        - Overall health score over time
        - Research quality rating over time
        - Timeline adherence rating over time
        
        Args:
            user_id: User ID
            start_date: Start date
            end_date: End date
            
        Returns:
            List of TimeSeriesSummary objects
        """
        series = []
        
        # Get assessments in date range
        assessments = self.db.query(JourneyAssessment).filter(
            JourneyAssessment.user_id == user_id,
            JourneyAssessment.assessment_date >= start_date,
            JourneyAssessment.assessment_date <= end_date
        ).order_by(JourneyAssessment.assessment_date.asc()).all()
        
        if not assessments:
            return series
        
        # Overall progress rating time-series
        overall_points = []
        for assessment in assessments:
            if assessment.overall_progress_rating is not None:
                # Convert 1-10 scale to 0-100 for consistency
                score = (assessment.overall_progress_rating / 10) * 100
                overall_points.append(TimeSeriesPoint(
                    date=assessment.assessment_date,
                    value=float(score),
                    metadata={
                        "assessment_id": str(assessment.id),
                        "assessment_type": assessment.assessment_type,
                        "raw_rating": assessment.overall_progress_rating
                    }
                ))
        
        if overall_points:
            series.append(self._create_time_series_summary(
                metric_name="journey_health_overall_score",
                points=overall_points
            ))
        
        # Research quality rating time-series
        research_points = []
        for assessment in assessments:
            if assessment.research_quality_rating is not None:
                score = (assessment.research_quality_rating / 10) * 100
                research_points.append(TimeSeriesPoint(
                    date=assessment.assessment_date,
                    value=float(score),
                    metadata={
                        "assessment_id": str(assessment.id),
                        "raw_rating": assessment.research_quality_rating
                    }
                ))
        
        if research_points:
            series.append(self._create_time_series_summary(
                metric_name="journey_health_research_quality",
                points=research_points
            ))
        
        # Timeline adherence rating time-series
        adherence_points = []
        for assessment in assessments:
            if assessment.timeline_adherence_rating is not None:
                score = (assessment.timeline_adherence_rating / 10) * 100
                adherence_points.append(TimeSeriesPoint(
                    date=assessment.assessment_date,
                    value=float(score),
                    metadata={
                        "assessment_id": str(assessment.id),
                        "raw_rating": assessment.timeline_adherence_rating
                    }
                ))
        
        if adherence_points:
            series.append(self._create_time_series_summary(
                metric_name="journey_health_timeline_adherence",
                points=adherence_points
            ))
        
        return series
    
    def _compute_status_indicators(
        self,
        user_id: UUID,
        timeline_id: Optional[UUID],
        timeline_series: List[TimeSeriesSummary],
        health_series: List[TimeSeriesSummary]
    ) -> List[StatusIndicator]:
        """
        Compute status indicators from aggregated data.
        
        Args:
            user_id: User ID
            timeline_id: Optional timeline ID
            timeline_series: Timeline progress time-series
            health_series: Journey health time-series
            
        Returns:
            List of StatusIndicator objects
        """
        indicators = []
        
        # Timeline progress indicator
        completion_series = next(
            (s for s in timeline_series if s.metric_name == "timeline_completion_percentage"),
            None
        )
        if completion_series and completion_series.current_value is not None:
            value = completion_series.current_value
            if value >= 80:
                status = "excellent"
                message = "Timeline completion is on track"
            elif value >= 60:
                status = "good"
                message = "Timeline completion is progressing well"
            elif value >= 40:
                status = "fair"
                message = "Timeline completion needs attention"
            elif value >= 20:
                status = "concerning"
                message = "Timeline completion is behind schedule"
            else:
                status = "critical"
                message = "Timeline completion is significantly behind"
            
            indicators.append(StatusIndicator(
                name="timeline_completion",
                value=value,
                status=status,
                message=message
            ))
        
        # Delay indicator
        delay_series = next(
            (s for s in timeline_series if s.metric_name == "milestone_delay_days"),
            None
        )
        if delay_series and delay_series.average is not None:
            avg_delay = delay_series.average
            if avg_delay <= 0:
                status = "excellent"
                message = "No delays on average"
            elif avg_delay <= 7:
                status = "good"
                message = "Minor delays on average"
            elif avg_delay <= 14:
                status = "fair"
                message = "Moderate delays on average"
            elif avg_delay <= 30:
                status = "concerning"
                message = "Significant delays on average"
            else:
                status = "critical"
                message = "Severe delays on average"
            
            indicators.append(StatusIndicator(
                name="average_delay",
                value=avg_delay,
                status=status,
                message=message
            ))
        
        # Overall health indicator
        health_series_overall = next(
            (s for s in health_series if s.metric_name == "journey_health_overall_score"),
            None
        )
        if health_series_overall and health_series_overall.current_value is not None:
            value = health_series_overall.current_value
            if value >= 80:
                status = "excellent"
                message = "Journey health is excellent"
            elif value >= 65:
                status = "good"
                message = "Journey health is good"
            elif value >= 50:
                status = "fair"
                message = "Journey health is fair"
            elif value >= 35:
                status = "concerning"
                message = "Journey health needs attention"
            else:
                status = "critical"
                message = "Journey health requires immediate attention"
            
            indicators.append(StatusIndicator(
                name="journey_health_overall",
                value=value,
                status=status,
                message=message
            ))
        
        # Health trend indicator
        if health_series_overall and len(health_series_overall.points) >= 2:
            trend = health_series_overall.trend
            if trend == "increasing":
                indicators.append(StatusIndicator(
                    name="journey_health_trend",
                    value=trend,
                    status="good",
                    message="Journey health is improving"
                ))
            elif trend == "decreasing":
                indicators.append(StatusIndicator(
                    name="journey_health_trend",
                    value=trend,
                    status="concerning",
                    message="Journey health is declining"
                ))
            else:
                indicators.append(StatusIndicator(
                    name="journey_health_trend",
                    value=trend or "stable",
                    status="fair",
                    message="Journey health is stable"
                ))
        
        return indicators
    
    def _create_time_series_summary(
        self,
        metric_name: str,
        points: List[TimeSeriesPoint]
    ) -> TimeSeriesSummary:
        """
        Create a TimeSeriesSummary from points.
        
        Args:
            metric_name: Name of the metric
            points: List of time series points
            
        Returns:
            TimeSeriesSummary object
        """
        if not points:
            return TimeSeriesSummary(
                metric_name=metric_name,
                points=[],
                current_value=None,
                trend=None,
                average=None,
                min_value=None,
                max_value=None
            )
        
        values = [p.value for p in points]
        current_value = points[-1].value if points else None
        
        # Compute trend (comparing last 3 points if available)
        trend = None
        if len(points) >= 3:
            recent_values = [p.value for p in points[-3:]]
            if recent_values[2] > recent_values[0]:
                trend = "increasing"
            elif recent_values[2] < recent_values[0]:
                trend = "decreasing"
            else:
                trend = "stable"
        elif len(points) == 2:
            if points[1].value > points[0].value:
                trend = "increasing"
            elif points[1].value < points[0].value:
                trend = "decreasing"
            else:
                trend = "stable"
        
        return TimeSeriesSummary(
            metric_name=metric_name,
            points=points,
            current_value=current_value,
            trend=trend,
            average=sum(values) / len(values) if values else None,
            min_value=min(values) if values else None,
            max_value=max(values) if values else None
        )
    
    def _generate_summary(
        self,
        timeline_series: List[TimeSeriesSummary],
        health_series: List[TimeSeriesSummary],
        status_indicators: List[StatusIndicator]
    ) -> Dict[str, Any]:
        """
        Generate overall summary from aggregated data.
        
        Args:
            timeline_series: Timeline progress time-series
            health_series: Journey health time-series
            status_indicators: Status indicators
            
        Returns:
            Summary dictionary
        """
        summary = {
            "has_timeline_data": len(timeline_series) > 0,
            "has_health_data": len(health_series) > 0,
            "total_metrics": len(timeline_series) + len(health_series),
            "total_indicators": len(status_indicators),
            "critical_indicators": [
                ind.name for ind in status_indicators if ind.status == "critical"
            ],
            "concerning_indicators": [
                ind.name for ind in status_indicators if ind.status == "concerning"
            ],
        }
        
        # Add latest values
        if timeline_series:
            completion = next(
                (s for s in timeline_series if s.metric_name == "timeline_completion_percentage"),
                None
            )
            if completion and completion.current_value is not None:
                summary["current_completion_percentage"] = completion.current_value
        
        if health_series:
            health = next(
                (s for s in health_series if s.metric_name == "journey_health_overall_score"),
                None
            )
            if health and health.current_value is not None:
                summary["current_health_score"] = health.current_value
        
        return summary
    
    def _compute_timeline_status(
        self,
        committed_timeline: CommittedTimeline,
        milestones: List[TimelineMilestone],
        progress_events: List[ProgressEvent]
    ) -> str:
        """
        Compute overall timeline status: on_track | delayed | completed.
        
        Rules:
        - completed: All milestones are completed
        - delayed: Any critical milestone is overdue OR >20% milestones overdue
        - on_track: Otherwise
        
        Args:
            committed_timeline: Committed timeline
            milestones: List of milestones
            progress_events: List of progress events
            
        Returns:
            Status string: "on_track", "delayed", or "completed"
        """
        if not milestones:
            return "on_track"
        
        # Check if all milestones are completed
        all_completed = all(m.is_completed for m in milestones)
        if all_completed:
            return "completed"
        
        # Check for delays
        today = date.today()
        overdue_count = 0
        overdue_critical_count = 0
        
        for milestone in milestones:
            if milestone.target_date and not milestone.is_completed:
                if milestone.target_date < today:
                    overdue_count += 1
                    if milestone.is_critical:
                        overdue_critical_count += 1
        
        # Determine status
        if overdue_critical_count > 0:
            return "delayed"
        
        overdue_ratio_threshold = RiskFusionEngine.get_overdue_ratio_delayed_threshold(self.db)
        overdue_threshold = len(milestones) * overdue_ratio_threshold
        if overdue_count > overdue_threshold:
            return "delayed"
        
        return "on_track"
    
    def _aggregate_milestone_completion(
        self,
        milestones: List[TimelineMilestone]
    ) -> Dict[str, Any]:
        """
        Aggregate milestone completion metrics.
        
        Args:
            milestones: List of milestones
            
        Returns:
            Dictionary with completion metrics
        """
        if not milestones:
            return {
                "total": 0,
                "completed": 0,
                "pending": 0,
                "completion_percentage": 0.0
            }
        
        total = len(milestones)
        completed = sum(1 for m in milestones if m.is_completed)
        pending = total - completed
        completion_percentage = (completed / total) * 100 if total > 0 else 0.0
        
        return {
            "total": total,
            "completed": completed,
            "pending": pending,
            "completion_percentage": round(completion_percentage, 1)
        }
    
    def _aggregate_delay_metrics(
        self,
        milestones: List[TimelineMilestone],
        progress_events: List[ProgressEvent]
    ) -> Dict[str, Any]:
        """
        Aggregate delay counts and overdue milestones.
        
        Args:
            milestones: List of milestones
            progress_events: List of progress events
            
        Returns:
            Dictionary with delay metrics
        """
        today = date.today()
        delays = []
        overdue_count = 0
        overdue_critical_count = 0
        
        for milestone in milestones:
            if milestone.target_date:
                if milestone.is_completed and milestone.actual_completion_date:
                    # Calculate delay for completed milestone
                    delay_days = (milestone.actual_completion_date - milestone.target_date).days
                    delays.append(delay_days)
                elif not milestone.is_completed:
                    # Check if overdue
                    delay_days = (today - milestone.target_date).days
                    if delay_days > 0:
                        overdue_count += 1
                        if milestone.is_critical:
                            overdue_critical_count += 1
                        delays.append(delay_days)
        
        total_delays = len(delays)
        average_delay = sum(delays) / len(delays) if delays else 0.0
        max_delay = max(delays) if delays else 0
        
        return {
            "total_delays": total_delays,
            "overdue_count": overdue_count,
            "overdue_critical_count": overdue_critical_count,
            "average_delay": round(average_delay, 1),
            "max_delay": max_delay
        }
    
    def _aggregate_health_dimensions(
        self,
        latest_assessment: Optional[JourneyAssessment]
    ) -> Dict[str, Any]:
        """
        Aggregate journey health dimensions from latest assessment.
        
        Args:
            latest_assessment: Latest journey assessment
            
        Returns:
            Dictionary with health metrics
        """
        if not latest_assessment:
            return {
                "overall_score": None,
                "dimensions": {}
            }
        
        # Convert 1-10 scale to 0-100 for overall score
        overall_score = None
        if latest_assessment.overall_progress_rating is not None:
            overall_score = (latest_assessment.overall_progress_rating / 10) * 100
        
        # Build dimensions dictionary
        dimensions = {}
        
        if latest_assessment.research_quality_rating is not None:
            dimensions["research_quality"] = (latest_assessment.research_quality_rating / 10) * 100
        
        if latest_assessment.timeline_adherence_rating is not None:
            dimensions["timeline_adherence"] = (latest_assessment.timeline_adherence_rating / 10) * 100
        
        return {
            "overall_score": round(overall_score, 1) if overall_score is not None else None,
            "dimensions": dimensions
        }
    
    def _generate_longitudinal_summary(
        self,
        committed_timeline: CommittedTimeline,
        milestones: List[TimelineMilestone],
        progress_events: List[ProgressEvent],
        latest_assessment: Optional[JourneyAssessment]
    ) -> Dict[str, Any]:
        """
        Generate longitudinal summary object.
        
        Args:
            committed_timeline: Committed timeline
            milestones: List of milestones
            progress_events: List of progress events
            latest_assessment: Latest journey assessment
            
        Returns:
            Dictionary with longitudinal summary
        """
        today = date.today()
        
        # Timeline duration metrics
        timeline_duration_days = None
        elapsed_days = None
        duration_progress_percentage = None
        
        if committed_timeline.committed_date and committed_timeline.target_completion_date:
            timeline_duration_days = (committed_timeline.target_completion_date - committed_timeline.committed_date).days
            elapsed_days = (today - committed_timeline.committed_date).days
            if timeline_duration_days > 0:
                duration_progress_percentage = (elapsed_days / timeline_duration_days) * 100
        
        # Event counts by type
        event_counts = {}
        for event in progress_events:
            event_type = event.event_type
            event_counts[event_type] = event_counts.get(event_type, 0) + 1
        
        # Milestone completion timeline (first and last completion dates)
        completed_milestones = [m for m in milestones if m.is_completed and m.actual_completion_date]
        first_completion_date = None
        last_completion_date = None
        
        if completed_milestones:
            completion_dates = [m.actual_completion_date for m in completed_milestones]
            first_completion_date = min(completion_dates)
            last_completion_date = max(completion_dates)
        
        # Assessment info
        assessment_info = None
        if latest_assessment:
            assessment_info = {
                "assessment_date": latest_assessment.assessment_date.isoformat(),
                "assessment_type": latest_assessment.assessment_type,
                "overall_rating": latest_assessment.overall_progress_rating
            }
        
        return {
            "timeline_committed_date": committed_timeline.committed_date.isoformat() if committed_timeline.committed_date else None,
            "target_completion_date": committed_timeline.target_completion_date.isoformat() if committed_timeline.target_completion_date else None,
            "timeline_duration_days": timeline_duration_days,
            "elapsed_days": elapsed_days,
            "duration_progress_percentage": round(duration_progress_percentage, 1) if duration_progress_percentage else None,
            "total_progress_events": len(progress_events),
            "event_counts_by_type": event_counts,
            "first_milestone_completion_date": first_completion_date.isoformat() if first_completion_date else None,
            "last_milestone_completion_date": last_completion_date.isoformat() if last_completion_date else None,
            "latest_assessment": assessment_info
        }

    def _generate_temporal_analysis(
        self,
        user_id: UUID,
        committed_timeline: CommittedTimeline,
        progress_events: List[ProgressEvent],
        milestones: List[TimelineMilestone],
        longitudinal_summary: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Generate temporal analysis using TemporalEngine.

        Fetches historical snapshots and calls the temporal engine
        to analyze trends, drift, velocity, and patterns.

        Args:
            user_id: User ID
            committed_timeline: Committed timeline
            progress_events: List of progress events
            milestones: List of milestones
            longitudinal_summary: Longitudinal summary dict

        Returns:
            Temporal analysis dictionary or None if insufficient data
        """
        # Fetch historical snapshots for this user
        snapshots = self.db.query(AnalyticsSnapshot).filter(
            AnalyticsSnapshot.user_id == user_id
        ).order_by(AnalyticsSnapshot.created_at.asc()).all()

        # Convert to dictionaries
        snapshot_dicts = [
            {
                "id": str(s.id),
                "user_id": str(s.user_id),
                "timeline_version": s.timeline_version,
                "summary_json": s.summary_json,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in snapshots
        ]

        # Convert progress events to dictionaries
        event_dicts = [
            {
                "id": str(e.id),
                "user_id": str(e.user_id),
                "milestone_id": str(e.milestone_id) if e.milestone_id else None,
                "event_type": e.event_type,
                "title": e.title,
                "description": e.description,
                "event_date": e.event_date.isoformat() if e.event_date else None,
                "impact_level": e.impact_level,
            }
            for e in progress_events
        ]

        # Convert milestones to dictionaries
        milestone_dicts = [
            {
                "id": str(m.id),
                "title": m.title,
                "is_completed": m.is_completed,
                "is_critical": m.is_critical,
                "target_date": m.target_date.isoformat() if m.target_date else None,
                "actual_completion_date": m.actual_completion_date.isoformat() if m.actual_completion_date else None,
                "stage_title": None,  # Would need to join with stage
            }
            for m in milestones
        ]

        # Calculate total duration in months
        total_duration_months = None
        if longitudinal_summary.get("timeline_duration_days"):
            total_duration_months = longitudinal_summary["timeline_duration_days"] // 30

        # Call temporal engine
        return self.temporal_engine.analyze_trends(
            user_id=user_id,
            snapshots=snapshot_dicts,
            progress_events=event_dicts,
            milestones=milestone_dicts,
            total_duration_months=total_duration_months,
        )