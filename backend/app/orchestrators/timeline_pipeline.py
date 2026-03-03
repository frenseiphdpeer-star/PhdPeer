"""Timeline pipeline domain logic."""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from uuid import UUID

from app.models.draft_timeline import DraftTimeline
from app.models.timeline_milestone import TimelineMilestone
from app.models.timeline_stage import TimelineStage
from app.repositories.timeline_repository import TimelineRepository
from app.services.timeline_intelligence_engine import (
    Dependency,
    DetectedStage,
    DurationEstimate,
    ExtractedMilestone,
    StageType,
    TimelineIntelligenceEngine,
)


class TimelinePipelineError(Exception):
    """Raised for timeline pipeline execution failures."""


@dataclass
class TimelinePipelineResult:
    """Structured output from timeline pipeline execution."""

    draft_timeline: DraftTimeline
    stage_records: List[TimelineStage]
    milestone_records: List[TimelineMilestone]
    detected_stages: List[DetectedStage]
    extracted_milestones: List[ExtractedMilestone]
    duration_estimates: List[DurationEstimate]
    dependencies: List[Dependency]


class TimelinePipeline:
    """Encapsulates timeline generation domain flow."""

    STATUS_DRAFT = "DRAFT"

    def __init__(self, repository: TimelineRepository, intelligence_engine: TimelineIntelligenceEngine):
        self.repository = repository
        self.intelligence_engine = intelligence_engine

    def generate_draft_timeline(
        self,
        baseline_id: UUID,
        user_id: UUID,
        title: Optional[str],
        description: Optional[str],
        version_number: str,
    ) -> TimelinePipelineResult:
        baseline = self.repository.get_baseline_for_user(baseline_id, user_id)
        if not baseline:
            raise TimelinePipelineError("Baseline not found for user")

        resolved_title = title or f"Draft Timeline: {baseline.program_name}"
        resolved_description = description or (
            f"Draft timeline for {baseline.program_name} at {baseline.institution}. "
            "Generated from baseline requirements and program structure."
        )

        # Document path: baseline has document with text
        document = None
        if baseline.document_artifact_id:
            document = self.repository.get_document_artifact(baseline.document_artifact_id)

        if document and document.document_text:
            detected_stages = self.intelligence_engine.detect_stages(
                text=document.document_text,
                section_map=document.section_map_json,
            )
            extracted_milestones = self.intelligence_engine.extract_milestones(
                text=document.document_text,
                section_map=document.section_map_json,
            )
            duration_estimates = self.intelligence_engine.estimate_durations(
                text=document.document_text,
                section_map=document.section_map_json,
            )
            dependencies = self.intelligence_engine.map_dependencies(
                text=document.document_text,
                section_map=document.section_map_json,
            )
        else:
            # Cold start: no document or no text — generate from baseline metadata
            from app.services.llm.cold_start import generate_cold_start_timeline
            cold_result = generate_cold_start_timeline(
                field_of_study=baseline.field_of_study,
                institution=baseline.institution,
                program_name=baseline.program_name,
                start_date=baseline.start_date.isoformat() if baseline.start_date else None,
                total_duration_months=baseline.total_duration_months,
            )
            detected_stages, extracted_milestones, duration_estimates, dependencies = (
                self._cold_start_to_pipeline_data(cold_result)
            )

        draft = self.repository.create_draft_timeline(
            user_id=user_id,
            baseline_id=baseline.id,
            title=resolved_title,
            description=resolved_description,
            version_number=version_number,
            notes=f"Status: {self.STATUS_DRAFT}",
        )

        stage_records = self._create_stage_records(draft.id, detected_stages, duration_estimates)
        milestone_records = self._create_milestone_records(stage_records, extracted_milestones)

        return TimelinePipelineResult(
            draft_timeline=draft,
            stage_records=stage_records,
            milestone_records=milestone_records,
            detected_stages=detected_stages,
            extracted_milestones=extracted_milestones,
            duration_estimates=duration_estimates,
            dependencies=dependencies,
        )

    def _cold_start_to_pipeline_data(
        self, cold_result: Dict[str, Any]
    ) -> tuple[List[DetectedStage], List[ExtractedMilestone], List[DurationEstimate], List[Dependency]]:
        """Convert cold-start generator output to pipeline dataclasses."""
        detected_stages: List[DetectedStage] = []
        for i, s in enumerate(cold_result.get("stages", [])):
            st = (s.get("stage_type") or "other").lower().replace(" ", "_")
            try:
                stage_type = StageType(st) if st in [e.value for e in StageType] else StageType.OTHER
            except (ValueError, TypeError):
                stage_type = StageType.OTHER
            detected_stages.append(
                DetectedStage(
                    stage_type=stage_type,
                    title=str(s.get("title", f"Stage {i+1}")).strip(),
                    description=str(s.get("description", "")).strip(),
                    confidence=float(s.get("confidence", 0.8)),
                    order_hint=int(s.get("order_hint", i + 1)),
                )
            )
        # Sort by order_hint
        detected_stages.sort(key=lambda x: x.order_hint)

        extracted_milestones: List[ExtractedMilestone] = []
        for m in cold_result.get("milestones", []):
            extracted_milestones.append(
                ExtractedMilestone(
                    name=str(m.get("name", "")).strip(),
                    description=str(m.get("description", "")).strip(),
                    stage=str(m.get("stage", "")).strip(),
                    milestone_type=str(m.get("milestone_type", "deliverable")).lower(),
                    evidence_snippet="",
                    is_critical=bool(m.get("is_critical", False)),
                    confidence=float(m.get("confidence", 0.8)),
                )
            )

        duration_estimates: List[DurationEstimate] = []
        for d in cold_result.get("durations", []):
            duration_estimates.append(
                DurationEstimate(
                    item_description=str(d.get("item_description", "")).strip(),
                    item_type=(d.get("item_type") or "stage").lower(),
                    duration_weeks_min=int(d.get("duration_weeks_min", 4)),
                    duration_weeks_max=int(d.get("duration_weeks_max", 8)),
                    duration_months_min=int(d.get("duration_months_min", 1)),
                    duration_months_max=int(d.get("duration_months_max", 2)),
                    confidence="medium" if float(d.get("confidence", 0.5)) >= 0.6 else "low",
                    basis=str(d.get("basis", "default")).strip() or "default",
                )
            )
        # If cold start didn't return durations per stage, add from stages
        if not duration_estimates and detected_stages:
            for stage in detected_stages:
                duration_estimates.append(
                    DurationEstimate(
                        item_description=stage.title,
                        item_type="stage",
                        duration_weeks_min=8,
                        duration_weeks_max=24,
                        duration_months_min=2,
                        duration_months_max=6,
                        confidence="medium",
                        basis="default",
                    )
                )

        dependencies_list: List[Dependency] = []
        for dep in cold_result.get("dependencies", []):
            dependencies_list.append(
                Dependency(
                    dependent_item=str(dep.get("dependent_item", dep.get("dependent", ""))).strip(),
                    depends_on_item=str(dep.get("depends_on_item", dep.get("depends_on", ""))).strip(),
                    dependency_type=str(dep.get("dependency_type", dep.get("type", "finish_to_start"))).strip(),
                    confidence=float(dep.get("confidence", 0.8)),
                    reason=str(dep.get("reason", "")).strip(),
                )
            )

        return detected_stages, extracted_milestones, duration_estimates, dependencies_list

    def _create_stage_records(
        self,
        draft_timeline_id: UUID,
        detected_stages: List[DetectedStage],
        duration_estimates: List[DurationEstimate],
    ) -> List[TimelineStage]:
        duration_map = {
            est.item_description.lower(): (est.duration_months_min + est.duration_months_max) // 2
            for est in duration_estimates
            if est.item_type == "stage"
        }

        stage_records: List[TimelineStage] = []
        for order, stage in enumerate(detected_stages, start=1):
            duration = self._resolve_stage_duration(stage, duration_map)
            stage_record = self.repository.create_stage(
                draft_timeline_id=draft_timeline_id,
                title=stage.title,
                description=stage.description,
                stage_order=order,
                duration_months=duration,
                status="not_started",
                notes=f"Confidence: {stage.confidence:.2f}",
            )
            stage_records.append(stage_record)
        return stage_records

    def _create_milestone_records(
        self,
        stage_records: List[TimelineStage],
        extracted_milestones: List[ExtractedMilestone],
    ) -> List[TimelineMilestone]:
        if not stage_records:
            return []

        milestone_count_by_stage = {stage.id: 0 for stage in stage_records}
        milestone_records: List[TimelineMilestone] = []

        for milestone in extracted_milestones:
            assigned_stage = self._assign_stage(stage_records, milestone)
            milestone_count_by_stage[assigned_stage.id] += 1
            milestone_record = self.repository.create_milestone(
                timeline_stage_id=assigned_stage.id,
                title=milestone.name,
                description=milestone.description,
                milestone_order=milestone_count_by_stage[assigned_stage.id],
                is_critical=milestone.is_critical,
                deliverable_type=milestone.milestone_type,
                notes=f"Confidence: {milestone.confidence:.2f}",
            )
            milestone_records.append(milestone_record)

        return milestone_records

    def _assign_stage(
        self,
        stage_records: List[TimelineStage],
        milestone: ExtractedMilestone,
    ) -> TimelineStage:
        normalized_stage_text = (milestone.stage or "").lower()
        for stage in stage_records:
            if stage.title.lower() in normalized_stage_text or normalized_stage_text in stage.title.lower():
                return stage
        return stage_records[0]

    def _resolve_stage_duration(
        self,
        stage: DetectedStage,
        duration_map: dict[str, int],
    ) -> int:
        for key, duration in duration_map.items():
            if stage.title.lower() in key or stage.stage_type.value in key:
                return duration
        defaults = {
            StageType.COURSEWORK: 18,
            StageType.LITERATURE_REVIEW: 6,
            StageType.METHODOLOGY: 4,
            StageType.DATA_COLLECTION: 8,
            StageType.ANALYSIS: 6,
            StageType.WRITING: 12,
            StageType.SUBMISSION: 3,
            StageType.DEFENSE: 3,
            StageType.PUBLICATION: 6,
            StageType.OTHER: 3,
        }
        return defaults.get(stage.stage_type, 6)
