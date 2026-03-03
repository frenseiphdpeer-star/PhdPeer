"""
Preparation-recommendation engine for the Opportunity Matching Engine.

Given a match prediction and the input signals, generates actionable
preparation recommendations that help the researcher maximise their
chance of acceptance.

Recommendations are **rule-based** (no LLM dependency) so they are
deterministic, fast, and testable.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional

from app.ml.opportunity_matching.features import MatchRecord

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Recommendation:
    """A single preparation recommendation."""

    category: str          # e.g. "timeline", "writing", "networking"
    priority: str          # "high" | "medium" | "low"
    message: str           # human-readable advice
    rationale: str         # why this recommendation was triggered

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "priority": self.priority,
            "message": self.message,
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class PreparationPlan:
    """Full preparation plan for one opportunity match."""

    recommendations: List[Recommendation]
    readiness_label: str     # "ready" | "needs_preparation" | "stretch_goal"

    def to_dict(self) -> dict:
        return {
            "recommendations": [r.to_dict() for r in self.recommendations],
            "readiness_label": self.readiness_label,
        }


# ---------------------------------------------------------------------------
# Recommendation generator
# ---------------------------------------------------------------------------

def generate_recommendations(
    record: MatchRecord,
    *,
    success_probability: float,
    cosine_similarity: float,
    match_score: float,
) -> PreparationPlan:
    """
    Generate actionable preparation recommendations for a match.

    Rules are based on signal thresholds and produce deterministic output.
    """
    recs: List[Recommendation] = []

    # ── Timeline / deadline urgency ───────────────────────────────────
    days = record.days_to_deadline
    if days is not None and days < 14:
        recs.append(Recommendation(
            category="timeline",
            priority="high",
            message=(
                f"Deadline is in {int(days)} days. Prioritise this application "
                "immediately and allocate dedicated writing time."
            ),
            rationale=f"days_to_deadline={days} < 14",
        ))
    elif days is not None and days < 30:
        recs.append(Recommendation(
            category="timeline",
            priority="medium",
            message=(
                f"Deadline is in {int(days)} days. Begin drafting your "
                "application materials this week."
            ),
            rationale=f"days_to_deadline={days} < 30",
        ))

    # ── Low cosine similarity → improve proposal alignment ───────────
    if cosine_similarity < 0.4:
        recs.append(Recommendation(
            category="writing",
            priority="high",
            message=(
                "Your research profile has low semantic alignment with this "
                "opportunity. Revise your proposal to emphasise overlapping "
                "keywords, methods, and outcomes."
            ),
            rationale=f"cosine_similarity={cosine_similarity:.2f} < 0.4",
        ))
    elif cosine_similarity < 0.6:
        recs.append(Recommendation(
            category="writing",
            priority="medium",
            message=(
                "Moderate alignment detected. Strengthen your proposal by "
                "explicitly connecting your research goals to this "
                "opportunity's objectives."
            ),
            rationale=f"cosine_similarity={cosine_similarity:.2f} < 0.6",
        ))

    # ── Low prior success rate ────────────────────────────────────────
    psr = record.prior_success_rate
    if psr is not None and psr < 0.2:
        recs.append(Recommendation(
            category="track_record",
            priority="medium",
            message=(
                "Your prior acceptance rate is low. Consider seeking feedback "
                "on previous applications and applying to opportunities with "
                "higher alignment first to build momentum."
            ),
            rationale=f"prior_success_rate={psr:.2f} < 0.2",
        ))

    # ── Low timeline readiness ────────────────────────────────────────
    trs = record.timeline_readiness_score
    if trs is not None and trs < 0.3:
        recs.append(Recommendation(
            category="timeline",
            priority="high",
            message=(
                "Your current PhD timeline readiness is low. Ensure milestone "
                "obligations are on track before committing to this opportunity."
            ),
            rationale=f"timeline_readiness_score={trs:.2f} < 0.3",
        ))
    elif trs is not None and trs < 0.6:
        recs.append(Recommendation(
            category="timeline",
            priority="medium",
            message=(
                "Timeline readiness is moderate. Plan your workload carefully "
                "to accommodate this opportunity alongside current milestones."
            ),
            rationale=f"timeline_readiness_score={trs:.2f} < 0.6",
        ))

    # ── Discipline mismatch ───────────────────────────────────────────
    rd = record.researcher_discipline
    od = record.opportunity_discipline
    if rd and od and rd != od:
        recs.append(Recommendation(
            category="networking",
            priority="low",
            message=(
                f"This opportunity is in {od.replace('_', ' ')} while your "
                f"discipline is {rd.replace('_', ' ')}. Highlight "
                "interdisciplinary skills or seek a collaborator from the "
                "target field."
            ),
            rationale=f"discipline_mismatch: {rd} != {od}",
        ))

    # ── No prior applications ─────────────────────────────────────────
    pac = record.prior_application_count
    if pac is not None and pac == 0:
        recs.append(Recommendation(
            category="experience",
            priority="medium",
            message=(
                "This would be your first application. Review successful "
                "examples in your department and have your supervisor review "
                "your draft before submission."
            ),
            rationale="prior_application_count=0",
        ))

    # ── Low model confidence ──────────────────────────────────────────
    if success_probability < 0.2:
        recs.append(Recommendation(
            category="strategy",
            priority="low",
            message=(
                "The model estimates a low success probability. This may be a "
                "stretch goal – apply only if the opportunity aligns strongly "
                "with your long-term objectives."
            ),
            rationale=f"success_probability={success_probability:.2f} < 0.2",
        ))

    # ── Readiness label ───────────────────────────────────────────────
    if success_probability >= 0.5 and match_score >= 60:
        readiness = "ready"
    elif success_probability >= 0.25 or match_score >= 40:
        readiness = "needs_preparation"
    else:
        readiness = "stretch_goal"

    # If no specific recommendations triggered, affirm readiness
    if not recs:
        recs.append(Recommendation(
            category="general",
            priority="low",
            message=(
                "Your profile aligns well with this opportunity. Proceed with "
                "a standard application and ensure your materials are polished."
            ),
            rationale="all_signals_positive",
        ))

    return PreparationPlan(
        recommendations=recs,
        readiness_label=readiness,
    )
