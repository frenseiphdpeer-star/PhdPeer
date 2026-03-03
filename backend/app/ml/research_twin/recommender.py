"""
Personalised recommendation engine for the AI Research Twin.

Takes LSTM productivity forecasts + user embeddings and generates
the four output targets:

  1. **productive_time_window**         – peak-hours / peak-days
  2. **procrastination_pattern**        – detected delay patterns
  3. **optimal_submission_window**      – best time-of-week to submit
  4. **personalized_nudge_recommendations** – actionable nudges
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np

from app.ml.research_twin.config import (
    RECOMMENDER_CFG,
    RecommenderConfig,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Output containers
# ---------------------------------------------------------------------------

@dataclass
class TimeWindow:
    """A contiguous productive / submission window."""

    start_hour: int              # 0–23
    end_hour: int                # 0–23
    day_of_week: Optional[int]   # 0=Mon … 6=Sun, None if daily-agg
    score: float                 # 0–1 productivity / suitability

    def to_dict(self) -> Dict[str, Any]:
        return {
            "start_hour": self.start_hour,
            "end_hour": self.end_hour,
            "day_of_week": self.day_of_week,
            "day_name": _DOW_NAMES.get(self.day_of_week, "any"),
            "score": round(self.score, 4),
        }


@dataclass
class ProcrastinationPattern:
    """A detected procrastination pattern."""

    pattern_type: str            # e.g. "deadline-surge", "morning-avoidance"
    description: str
    severity: str                # "high", "medium", "low"
    evidence: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pattern_type": self.pattern_type,
            "description": self.description,
            "severity": self.severity,
            "evidence": self.evidence,
        }


@dataclass
class Nudge:
    """A personalised nudge recommendation."""

    category: str                # e.g. "timing", "consistency", "engagement"
    message: str
    priority: str                # "high", "medium", "low"
    trigger: str                 # when to deliver the nudge

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "message": self.message,
            "priority": self.priority,
            "trigger": self.trigger,
        }


@dataclass
class TwinRecommendation:
    """Full recommendation output for one researcher."""

    researcher_id: str
    productive_time_windows: List[TimeWindow]
    procrastination_patterns: List[ProcrastinationPattern]
    optimal_submission_windows: List[TimeWindow]
    nudges: List[Nudge]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "researcher_id": self.researcher_id,
            "productive_time_window": [
                w.to_dict() for w in self.productive_time_windows
            ],
            "procrastination_pattern": [
                p.to_dict() for p in self.procrastination_patterns
            ],
            "optimal_submission_window": [
                w.to_dict() for w in self.optimal_submission_windows
            ],
            "personalized_nudge_recommendations": [
                n.to_dict() for n in self.nudges
            ],
        }


_DOW_NAMES = {
    0: "Monday", 1: "Tuesday", 2: "Wednesday", 3: "Thursday",
    4: "Friday", 5: "Saturday", 6: "Sunday",
}


# ---------------------------------------------------------------------------
# 1) Productive time windows
# ---------------------------------------------------------------------------

def detect_productive_windows(
    forecast: np.ndarray,
    *,
    cfg: RecommenderConfig | None = None,
) -> List[TimeWindow]:
    """
    Identify contiguous hourly windows where predicted productivity
    exceeds the threshold.

    Parameters
    ----------
    forecast : ndarray  shape (24,)  – hourly productivity scores 0–1
    """
    c = cfg or RECOMMENDER_CFG
    windows: List[TimeWindow] = []
    in_window = False
    start = 0

    for h in range(len(forecast)):
        if forecast[h] >= c.productive_threshold:
            if not in_window:
                start = h
                in_window = True
        else:
            if in_window:
                windows.append(TimeWindow(
                    start_hour=start,
                    end_hour=h - 1,
                    day_of_week=None,
                    score=float(forecast[start:h].mean()),
                ))
                in_window = False
    if in_window:
        windows.append(TimeWindow(
            start_hour=start,
            end_hour=len(forecast) - 1,
            day_of_week=None,
            score=float(forecast[start:].mean()),
        ))

    windows.sort(key=lambda w: w.score, reverse=True)
    return windows


# ---------------------------------------------------------------------------
# 2) Procrastination patterns
# ---------------------------------------------------------------------------

def detect_procrastination(
    forecast: np.ndarray,
    *,
    cfg: RecommenderConfig | None = None,
) -> List[ProcrastinationPattern]:
    """
    Detect procrastination patterns from hourly productivity forecast.

    Patterns detected:
      • **long-idle** – stretches of low productivity exceeding gap threshold
      • **late-surge** – sudden productivity spike after prolonged low period
      • **morning-avoidance** – low productivity in typical work hours (9–12)
    """
    c = cfg or RECOMMENDER_CFG
    patterns: List[ProcrastinationPattern] = []
    n = len(forecast)

    # --- long-idle ---
    idle_count = 0
    idle_stretches: List[int] = []
    for h in range(n):
        if forecast[h] < c.productive_threshold * 0.5:
            idle_count += 1
        else:
            if idle_count >= c.procrastination_gap_hours:
                idle_stretches.append(idle_count)
            idle_count = 0
    if idle_count >= c.procrastination_gap_hours:
        idle_stretches.append(idle_count)

    if idle_stretches:
        patterns.append(ProcrastinationPattern(
            pattern_type="long-idle",
            description=(
                f"Detected {len(idle_stretches)} stretch(es) of "
                f"{max(idle_stretches)}+ hours of very low activity."
            ),
            severity="high" if max(idle_stretches) >= 12 else "medium",
            evidence={"idle_stretches_hours": idle_stretches},
        ))

    # --- late-surge ---
    if n >= 12:
        first_half = forecast[: n // 2].mean()
        second_half = forecast[n // 2 :].mean()
        if (
            first_half < c.productive_threshold * 0.5
            and second_half >= c.productive_threshold
        ):
            patterns.append(ProcrastinationPattern(
                pattern_type="late-surge",
                description=(
                    "Low activity in early hours followed by a productivity "
                    "surge in later hours — may indicate deadline-driven behaviour."
                ),
                severity="medium",
                evidence={
                    "first_half_mean": round(float(first_half), 4),
                    "second_half_mean": round(float(second_half), 4),
                },
            ))

    # --- morning-avoidance ---
    if n >= 13:
        morning = forecast[9:13].mean() if n > 12 else 0.0
        overall = forecast.mean()
        if morning < overall * 0.5 and overall > 0:
            patterns.append(ProcrastinationPattern(
                pattern_type="morning-avoidance",
                description=(
                    "Productivity during typical work hours (9 AM – 12 PM) "
                    "is significantly below the daily average."
                ),
                severity="low",
                evidence={
                    "morning_mean": round(float(morning), 4),
                    "overall_mean": round(float(overall), 4),
                },
            ))

    return patterns


# ---------------------------------------------------------------------------
# 3) Optimal submission windows
# ---------------------------------------------------------------------------

def find_submission_windows(
    forecast: np.ndarray,
    *,
    cfg: RecommenderConfig | None = None,
) -> List[TimeWindow]:
    """
    The best times to submit deliverables = peak productivity windows
    *after* a productive stretch (rider: user has momentum).

    For simplicity, we select the top-N hours by productivity score.
    """
    c = cfg or RECOMMENDER_CFG
    n = len(forecast)

    scored: List[TimeWindow] = []
    for h in range(n):
        scored.append(TimeWindow(
            start_hour=h,
            end_hour=h,
            day_of_week=None,
            score=float(forecast[h]),
        ))

    scored.sort(key=lambda w: w.score, reverse=True)
    return scored[: c.top_submission_windows]


# ---------------------------------------------------------------------------
# 4) Personalised nudges
# ---------------------------------------------------------------------------

def generate_nudges(
    productive_windows: List[TimeWindow],
    procrastination: List[ProcrastinationPattern],
    submission_windows: List[TimeWindow],
    *,
    embedding_norm: float = 1.0,
    cfg: RecommenderConfig | None = None,
) -> List[Nudge]:
    """
    Generate actionable nudge recommendations based on detected patterns.
    """
    c = cfg or RECOMMENDER_CFG
    nudges: List[Nudge] = []

    # Nudge based on productive windows
    if productive_windows:
        best = productive_windows[0]
        nudges.append(Nudge(
            category="timing",
            message=(
                f"Your peak productivity is {best.start_hour}:00–"
                f"{best.end_hour + 1}:00. Schedule deep-work sessions "
                "during this window."
            ),
            priority="high",
            trigger="daily_start",
        ))

    # Nudge based on procrastination
    for pat in procrastination:
        if pat.pattern_type == "long-idle":
            nudges.append(Nudge(
                category="consistency",
                message=(
                    "You tend to have long idle stretches. Try the "
                    "Pomodoro technique (25 min work / 5 min break) to "
                    "maintain steady progress."
                ),
                priority="high",
                trigger="idle_detected",
            ))
        elif pat.pattern_type == "late-surge":
            nudges.append(Nudge(
                category="timing",
                message=(
                    "Your work pattern shows deadline-driven surges. "
                    "Starting earlier in the day could reduce stress and "
                    "improve output quality."
                ),
                priority="medium",
                trigger="morning",
            ))
        elif pat.pattern_type == "morning-avoidance":
            nudges.append(Nudge(
                category="engagement",
                message=(
                    "Consider warming up with lighter tasks (reading, "
                    "annotation) during morning hours to build momentum."
                ),
                priority="low",
                trigger="morning",
            ))

    # Nudge for submission timing
    if submission_windows:
        best_sub = submission_windows[0]
        nudges.append(Nudge(
            category="submission",
            message=(
                f"Based on your productivity cycle, the optimal time "
                f"to review and submit work is around "
                f"{best_sub.start_hour}:00."
            ),
            priority="medium",
            trigger="pre_deadline",
        ))

    # Low engagement nudge (from embedding norm — low norm ≈ low activity)
    if embedding_norm < 0.3:
        nudges.append(Nudge(
            category="engagement",
            message=(
                "Your recent activity level is lower than usual. "
                "Engaging with an opportunity or scheduling a supervisor "
                "check-in could help restart momentum."
            ),
            priority="high",
            trigger="weekly_review",
        ))

    return nudges[: c.max_nudges]


# ---------------------------------------------------------------------------
# Top-level recommendation generator
# ---------------------------------------------------------------------------

def generate_recommendation(
    researcher_id: str,
    forecast: np.ndarray,
    *,
    embedding_norm: float = 1.0,
    cfg: RecommenderConfig | None = None,
) -> TwinRecommendation:
    """
    Produce the full four-part recommendation for one researcher.

    Parameters
    ----------
    researcher_id : str
    forecast : ndarray  shape (output_size,)  – productivity scores 0–1
    embedding_norm : float
        L2 norm of the user embedding (proxy for activity level).
    """
    productive = detect_productive_windows(forecast, cfg=cfg)
    procrastination = detect_procrastination(forecast, cfg=cfg)
    submission = find_submission_windows(forecast, cfg=cfg)
    nudges = generate_nudges(
        productive, procrastination, submission,
        embedding_norm=embedding_norm, cfg=cfg,
    )

    return TwinRecommendation(
        researcher_id=researcher_id,
        productive_time_windows=productive,
        procrastination_patterns=procrastination,
        optimal_submission_windows=submission,
        nudges=nudges,
    )
