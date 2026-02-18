"""
Interpretability layer for all intelligence outputs.

Architecture: Intelligence layer must not expose any signal without evidence and
explanation. Every signal must carry:
- Evidence: contributing event_ids + time window (traceable to raw longitudinal events)
- Explanation: human-readable summary of why the signal was generated
- Recommendation: suggested user action

Signals cannot be displayed without the full explanation payload (for_display() only).
No signal should exist in the API without evidence and explanation.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID


@dataclass(frozen=True)
class TimeWindow:
    """Time window used to compute the signal (traceable evidence)."""
    start: datetime
    end: datetime


@dataclass
class Evidence:
    """Evidence supporting the signal; traceable back to raw events."""
    contributing_event_ids: List[UUID]  # LongitudinalEvent.event_id
    time_window: TimeWindow

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contributing_event_ids": [str(e) for e in self.contributing_event_ids],
            "time_window": {
                "start": self.time_window.start.isoformat(),
                "end": self.time_window.end.isoformat(),
            },
        }


@dataclass
class ExplanationPayload:
    """Required payload for any displayed signal."""
    evidence: Evidence
    explanation: str   # Human-readable summary of why signal was generated
    recommendation: str # Suggested user action

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evidence": self.evidence.to_dict(),
            "explanation": self.explanation,
            "recommendation": self.recommendation,
        }


# Signal type identifiers
SIGNAL_CONTINUITY_INDEX = "continuity_index"
SIGNAL_DROPOUT_RISK = "dropout_risk_signal"
SIGNAL_SUPERVISOR_ENGAGEMENT = "supervisor_engagement_alert"
SIGNAL_OPPORTUNITY_MATCH = "opportunity_match_score"

SIGNAL_TYPES = {
    SIGNAL_CONTINUITY_INDEX,
    SIGNAL_DROPOUT_RISK,
    SIGNAL_SUPERVISOR_ENGAGEMENT,
    SIGNAL_OPPORTUNITY_MATCH,
}


@dataclass
class InterpretableSignal:
    """
    A single intelligence signal with mandatory interpretability payload.
    Cannot be serialized for display without evidence, explanation, and recommendation.
    """
    signal_type: str
    value: Any  # Score, bool, or structured value
    explanation_payload: ExplanationPayload

    def __post_init__(self) -> None:
        if self.signal_type not in SIGNAL_TYPES:
            raise ValueError(f"Unknown signal_type: {self.signal_type}")
        if not self.explanation_payload.explanation.strip():
            raise ValueError("explanation cannot be empty")
        if not self.explanation_payload.recommendation.strip():
            raise ValueError("recommendation cannot be empty")
        if not isinstance(self.explanation_payload.evidence.time_window, TimeWindow):
            raise ValueError("evidence.time_window must be a TimeWindow")

    def for_display(self) -> Dict[str, Any]:
        """
        Serialize for API/dashboard. Only call when payload is complete.
        Signals cannot be displayed without this payload.
        """
        return {
            "signal_type": self.signal_type,
            "value": self._serialize_value(self.value),
            "evidence": self.explanation_payload.evidence.to_dict(),
            "explanation": self.explanation_payload.explanation,
            "recommendation": self.explanation_payload.recommendation,
        }

    @staticmethod
    def _serialize_value(v: Any) -> Any:
        if isinstance(v, (str, int, float, bool, type(None))):
            return v
        if isinstance(v, (list, tuple)):
            return [InterpretableSignal._serialize_value(x) for x in v]
        if isinstance(v, dict):
            return {k: InterpretableSignal._serialize_value(x) for k, x in v.items()}
        if hasattr(v, "isoformat"):
            return v.isoformat()
        return str(v)


def require_explanation_payload(signal: Optional[InterpretableSignal]) -> Dict[str, Any]:
    """
    Return signal payload for display only if explanation payload is present.
    Raises ValueError if signal is None or missing required payload (enforcement).
    """
    if signal is None:
        raise ValueError("Signal cannot be displayed without an interpretable signal")
    return signal.for_display()
