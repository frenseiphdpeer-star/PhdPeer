"""
Opportunity Matching Scorer – orchestration layer.

Combines:
  1. Embedding generation + cosine similarity
  2. Feature engineering
  3. LightGBM ranking prediction
  4. Urgency scoring
  5. Preparation recommendations

into a single ``score_match()`` call.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from app.ml.opportunity_matching.config import ALL_FEATURES, SCORING
from app.ml.opportunity_matching.embeddings import OpportunityEmbedder, get_embedder
from app.ml.opportunity_matching.features import MatchFeatureEngineer, MatchRecord
from app.ml.opportunity_matching.model import MatchPrediction, predict
from app.ml.opportunity_matching.recommender import (
    PreparationPlan,
    generate_recommendations,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class OpportunityMatchResult:
    """Full result for one researcher ↔ opportunity match."""

    match_score: float                  # 0–100
    success_probability: float          # 0–1
    cosine_similarity: float            # 0–1
    urgency_score: float                # 0–1
    preparation: PreparationPlan

    def to_dict(self) -> Dict[str, Any]:
        return {
            "match_score": round(self.match_score, 2),
            "success_probability": round(self.success_probability, 4),
            "cosine_similarity": round(self.cosine_similarity, 4),
            "urgency_score": round(self.urgency_score, 4),
            "preparation_recommendation": self.preparation.to_dict(),
        }


# ---------------------------------------------------------------------------
# Main scoring entry-point
# ---------------------------------------------------------------------------

def score_matches(
    records: Sequence[MatchRecord],
    *,
    _bundle: Optional[Dict[str, Any]] = None,
    _embedder: Optional[OpportunityEmbedder] = None,
) -> List[OpportunityMatchResult]:
    """
    Score one or more researcher ↔ opportunity pairs.

    If ``cosine_similarity`` is already set on the record it is used directly;
    otherwise embeddings must have been pre-computed by the caller (service
    layer).

    Parameters
    ----------
    records : sequence of MatchRecord
        Each record must already have ``cosine_similarity`` populated.
    _bundle : dict, optional
        Injected model bundle (for testing).
    """
    preds = predict(records, _bundle=_bundle)

    results: List[OpportunityMatchResult] = []
    for rec, pred in zip(records, preds):
        plan = generate_recommendations(
            rec,
            success_probability=pred.success_probability,
            cosine_similarity=pred.cosine_similarity,
            match_score=pred.match_score,
        )
        results.append(
            OpportunityMatchResult(
                match_score=pred.match_score,
                success_probability=pred.success_probability,
                cosine_similarity=pred.cosine_similarity,
                urgency_score=pred.urgency_score,
                preparation=plan,
            )
        )

    return results


def score_from_texts(
    researcher_text: str,
    opportunity_texts: List[str],
    *,
    records: Sequence[MatchRecord],
    _bundle: Optional[Dict[str, Any]] = None,
    _embedder: Optional[OpportunityEmbedder] = None,
) -> List[OpportunityMatchResult]:
    """
    Convenience: embed texts, compute cosine similarity, then score.

    ``records`` must have the same length as ``opportunity_texts`` and
    need NOT have ``cosine_similarity`` pre-filled – this function
    computes it from the texts.
    """
    embedder = _embedder or get_embedder()

    researcher_vec = embedder.encode(researcher_text)
    opp_vecs = embedder.encode(opportunity_texts)

    enriched: List[MatchRecord] = []
    for i, rec in enumerate(records):
        sim = embedder.cosine_similarity(researcher_vec[0], opp_vecs[i])
        enriched.append(MatchRecord(
            cosine_similarity=sim,
            stage_type=rec.stage_type,
            researcher_discipline=rec.researcher_discipline,
            opportunity_discipline=rec.opportunity_discipline,
            prior_success_rate=rec.prior_success_rate,
            prior_application_count=rec.prior_application_count,
            timeline_readiness_score=rec.timeline_readiness_score,
            days_to_deadline=rec.days_to_deadline,
            accepted=rec.accepted,
        ))

    return score_matches(enriched, _bundle=_bundle, _embedder=embedder)
