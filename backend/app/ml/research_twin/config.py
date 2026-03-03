"""
Configuration for the AI Research Twin behavioural modelling system.

All tunables are env-overridable so they can be changed per deployment
without touching code.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_BACKEND_ROOT = Path(__file__).resolve().parents[3]  # backend/
TWIN_ARTIFACTS_DIR: Path = Path(
    os.getenv(
        "TWIN_ARTIFACTS_DIR",
        str(_BACKEND_ROOT / "ml_artifacts" / "research_twin"),
    )
)

LSTM_FILENAME = "twin_lstm.pt"
METADATA_FILENAME = "twin_metadata.json"


# ---------------------------------------------------------------------------
# Input signal catalogue
# ---------------------------------------------------------------------------

# Raw behavioural event types recognised by the system.
EVENT_TYPES: List[str] = [
    "writing",                   # document writing activity
    "revision",                  # document revision / editing
    "opportunity_engagement",    # clicked / applied to opportunity
    "submission",                # submitted a deliverable
    "supervision",               # supervisor meeting / interaction
]

# Temporal feature channels derived from events.
FEATURE_CHANNELS: List[str] = [
    "writing_rate",              # writing events per hour
    "revision_density",          # revisions per hour
    "engagement_rate",           # opportunity interactions per hour
    "submission_rate",           # submissions per hour
    "supervision_rate",          # supervision events per hour
]

# Output prediction targets.
OUTPUT_NAMES: List[str] = [
    "productive_time_window",
    "procrastination_pattern",
    "optimal_submission_window",
    "personalized_nudge_recommendations",
]


# ---------------------------------------------------------------------------
# Temporal feature engineering
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TemporalFeatureConfig:
    """Controls how raw events are aggregated into temporal feature vectors."""

    # Bin size for temporal features (hours)
    bin_hours: int = int(os.getenv("TWIN_BIN_HOURS", "1"))

    # Rolling window size (bins) for smoothing
    rolling_window: int = int(os.getenv("TWIN_ROLLING_WIN", "3"))

    # Number of days of history to consider per user
    history_days: int = int(os.getenv("TWIN_HISTORY_DAYS", "90"))

    # Hours in a day (for cyclic encoding)
    hours_per_day: int = 24

    # Days in a week (for cyclic encoding)
    days_per_week: int = 7


TEMPORAL_CFG = TemporalFeatureConfig()


# ---------------------------------------------------------------------------
# Sequence / LSTM parameters
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SequenceConfig:
    """Controls how temporal features are shaped into LSTM sequences."""

    # Sequence length (time-steps fed to LSTM)
    seq_length: int = int(os.getenv("TWIN_SEQ_LEN", "168"))  # 1 week hourly

    # Stride between sequences (for training overlap)
    stride: int = int(os.getenv("TWIN_STRIDE", "24"))  # 1 day


SEQ_CFG = SequenceConfig()


@dataclass(frozen=True)
class LSTMConfig:
    """PyTorch LSTM hyper-parameters."""

    # Input features per time-step
    input_size: int = len(FEATURE_CHANNELS) + 4  # channels + 4 cyclic

    # Hidden state dimensionality (= embedding size)
    hidden_size: int = int(os.getenv("TWIN_HIDDEN", "64"))

    # Number of LSTM layers
    num_layers: int = int(os.getenv("TWIN_LAYERS", "2"))

    # Dropout between LSTM layers
    dropout: float = float(os.getenv("TWIN_DROPOUT", "0.2"))

    # Output heads: number of hourly bins to predict productivity
    output_size: int = int(os.getenv("TWIN_OUTPUT", "24"))  # next 24h

    # Training
    learning_rate: float = float(os.getenv("TWIN_LR", "0.001"))
    epochs: int = int(os.getenv("TWIN_EPOCHS", "30"))
    batch_size: int = int(os.getenv("TWIN_BATCH", "32"))
    random_state: int = 42


LSTM_CFG = LSTMConfig()


# ---------------------------------------------------------------------------
# Embedding & recommender
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EmbeddingConfig:
    """Controls user-embedding extraction."""

    # Dimensionality of the final user embedding
    embedding_dim: int = int(os.getenv("TWIN_EMBED_DIM", "64"))

    # PCA reduction (0 = skip)
    pca_components: int = int(os.getenv("TWIN_PCA", "0"))


EMBED_CFG = EmbeddingConfig()


@dataclass(frozen=True)
class RecommenderConfig:
    """Thresholds for nudge / recommendation generation."""

    # Minimum productivity score to be considered a "productive window"
    productive_threshold: float = float(
        os.getenv("TWIN_PROD_THRESH", "0.6")
    )

    # Procrastination gap threshold (hours of continuous low activity)
    procrastination_gap_hours: int = int(
        os.getenv("TWIN_PROCRAST_GAP", "8")
    )

    # Number of top submission windows to report
    top_submission_windows: int = int(
        os.getenv("TWIN_TOP_SUBMIT", "3")
    )

    # Maximum nudge recommendations
    max_nudges: int = int(os.getenv("TWIN_MAX_NUDGES", "5"))


RECOMMENDER_CFG = RecommenderConfig()
