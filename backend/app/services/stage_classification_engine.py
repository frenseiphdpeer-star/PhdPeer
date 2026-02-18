"""
Stage classification pipeline: infer current PhD stage from document text.

Returns a single suggested_stage, confidence_score, and reasoning_tokens (internal).
Uses TimelineIntelligenceEngine.detect_stages; picks the dominant/current stage.
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional

from app.services.timeline_intelligence_engine import (
    TimelineIntelligenceEngine,
    DetectedStage,
)


@dataclass
class StageInferenceResult:
    """Result of stage inference for one document."""

    suggested_stage: str
    confidence_score: float
    reasoning_tokens: List[str]  # internal evidence snippets


class StageClassificationEngine:
    """
    Infers current PhD stage from document content.
    Uses existing TimelineIntelligenceEngine; returns one suggested stage per document.
    """

    def __init__(self) -> None:
        self._engine = TimelineIntelligenceEngine()

    def infer_from_document(
        self,
        text: str,
        section_map: Optional[Dict[str, Any]] = None,
    ) -> StageInferenceResult:
        """
        Run stage inference on document text.

        Args:
            text: Normalized document text
            section_map: Optional section map (e.g. document_artifact.section_map_json)

        Returns:
            suggested_stage: Human-readable stage name (e.g. "Literature Review")
            confidence_score: 0.0 to 1.0
            reasoning_tokens: List of evidence strings (internal)
        """
        if not (text or "").strip():
            return StageInferenceResult(
                suggested_stage="Other Activities",
                confidence_score=0.0,
                reasoning_tokens=[],
            )
        detected = self._engine.detect_stages(text, section_map)
        if not detected:
            return StageInferenceResult(
                suggested_stage="Other Activities",
                confidence_score=0.0,
                reasoning_tokens=[],
            )
        # Pick the "current" stage: highest order_hint among those with best confidence,
        # or single highest-confidence stage (assume most advanced detected = current)
        best = max(
            detected,
            key=lambda s: (s.order_hint, s.confidence),
        )
        reasoning_tokens = []
        for e in (best.evidence or [])[:10]:
            reasoning_tokens.append(getattr(e, "text", str(e)))
        return StageInferenceResult(
            suggested_stage=best.title,
            confidence_score=round(best.confidence, 4),
            reasoning_tokens=reasoning_tokens,
        )
