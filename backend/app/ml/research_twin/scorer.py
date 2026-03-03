"""
Scorer (orchestration) for the AI Research Twin.

Composes the full pipeline:

    raw behaviour events
        → temporal feature vectors
            → sequence slicing
                → LSTM training / inference
                    → embedding extraction
                        → personalised recommendations
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from app.ml.research_twin.config import (
    EMBED_CFG,
    LSTM_CFG,
    RECOMMENDER_CFG,
    SEQ_CFG,
    TEMPORAL_CFG,
    EmbeddingConfig,
    LSTMConfig,
    RecommenderConfig,
    SequenceConfig,
    TemporalFeatureConfig,
)
from app.ml.research_twin.embedding import (
    EmbeddingAnalysis,
    UserEmbedding,
    analyse_embeddings,
    build_user_embedding,
    find_similar_users,
)
from app.ml.research_twin.lstm import (
    LSTMTrainingResult,
    ProductivityLSTM,
    extract_embeddings,
    predict_productivity,
    train_lstm,
)
from app.ml.research_twin.recommender import (
    TwinRecommendation,
    generate_recommendation,
)
from app.ml.research_twin.temporal import (
    BehaviourEvent,
    build_multi_researcher,
    build_temporal_features,
    slice_sequences,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pipeline result
# ---------------------------------------------------------------------------

@dataclass
class TwinAnalysis:
    """Complete output of the Research Twin pipeline."""

    training_result: Optional[LSTMTrainingResult]
    recommendations: Dict[str, TwinRecommendation]  # rid → rec
    embedding_analysis: Optional[EmbeddingAnalysis]
    n_events: int
    n_researchers: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "training_result": (
                self.training_result.to_dict()
                if self.training_result else None
            ),
            "recommendations": {
                rid: rec.to_dict()
                for rid, rec in self.recommendations.items()
            },
            "embedding_analysis": (
                self.embedding_analysis.to_dict()
                if self.embedding_analysis else None
            ),
            "n_events": self.n_events,
            "n_researchers": self.n_researchers,
        }


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def analyse(
    events: Sequence[BehaviourEvent],
    *,
    temporal_cfg: TemporalFeatureConfig | None = None,
    seq_cfg: SequenceConfig | None = None,
    lstm_cfg: LSTMConfig | None = None,
    embed_cfg: EmbeddingConfig | None = None,
    rec_cfg: RecommenderConfig | None = None,
    do_train: bool = True,
    save_model: bool = True,
) -> TwinAnalysis:
    """
    Run the full Research Twin pipeline from raw events to
    personalised recommendations.
    """
    t_cfg = temporal_cfg or TEMPORAL_CFG
    s_cfg = seq_cfg or SEQ_CFG
    l_cfg = lstm_cfg or LSTM_CFG
    e_cfg = embed_cfg or EMBED_CFG
    r_cfg = rec_cfg or RECOMMENDER_CFG

    # 1) Build per-researcher temporal features
    per_researcher = build_multi_researcher(events, cfg=t_cfg)

    if not per_researcher:
        return TwinAnalysis(
            training_result=None,
            recommendations={},
            embedding_analysis=None,
            n_events=len(events),
            n_researchers=0,
        )

    # 2) Slice sequences for all researchers (pooled for training)
    all_seqs: List[np.ndarray] = []
    researcher_seq_map: Dict[str, np.ndarray] = {}

    for rid, feat_df in per_researcher.items():
        seqs = slice_sequences(feat_df, seq_cfg=s_cfg)
        researcher_seq_map[rid] = seqs
        all_seqs.append(seqs)

    pooled = np.concatenate(all_seqs, axis=0)

    # 3) Train LSTM (on pooled sequences)
    training_result: Optional[LSTMTrainingResult] = None
    model: Optional[ProductivityLSTM] = None

    if do_train and len(pooled) >= 1:
        model, training_result = train_lstm(
            pooled, cfg=l_cfg, save=save_model,
        )

    # 4) Generate per-researcher forecasts, embeddings, and recommendations
    recommendations: Dict[str, TwinRecommendation] = {}
    user_embeddings: List[UserEmbedding] = []

    for rid, seqs in researcher_seq_map.items():
        # Productivity forecast (use last sequence)
        forecast = predict_productivity(seqs[-1:], model=model)
        forecast_1d = forecast[0]  # shape (output_size,)

        # Extract embeddings
        raw_embs = extract_embeddings(seqs, model=model)
        user_emb = build_user_embedding(rid, raw_embs, cfg=e_cfg)
        user_embeddings.append(user_emb)

        # Generate recommendations
        rec = generate_recommendation(
            rid,
            forecast_1d,
            embedding_norm=user_emb.norm,
            cfg=r_cfg,
        )
        recommendations[rid] = rec

    # 5) Embedding analysis
    emb_analysis = analyse_embeddings(user_embeddings)

    logger.info(
        "Research Twin analysis complete: %d researchers, %d events",
        len(per_researcher),
        len(events),
    )

    return TwinAnalysis(
        training_result=training_result,
        recommendations=recommendations,
        embedding_analysis=emb_analysis,
        n_events=len(events),
        n_researchers=len(per_researcher),
    )


def analyse_single(
    events: Sequence[BehaviourEvent],
    researcher_id: str,
    *,
    temporal_cfg: TemporalFeatureConfig | None = None,
    seq_cfg: SequenceConfig | None = None,
    lstm_cfg: LSTMConfig | None = None,
    embed_cfg: EmbeddingConfig | None = None,
    rec_cfg: RecommenderConfig | None = None,
    do_train: bool = True,
    save_model: bool = True,
) -> Optional[TwinRecommendation]:
    """Convenience: analyse and return recommendation for one researcher."""
    result = analyse(
        events,
        temporal_cfg=temporal_cfg,
        seq_cfg=seq_cfg,
        lstm_cfg=lstm_cfg,
        embed_cfg=embed_cfg,
        rec_cfg=rec_cfg,
        do_train=do_train,
        save_model=save_model,
    )
    return result.recommendations.get(researcher_id)
