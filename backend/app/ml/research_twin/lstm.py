"""
PyTorch LSTM model for researcher productivity-cycle modelling.

The model ingests temporal feature sequences (hourly bins with
event-rate channels + cyclic encodings) and learns to predict
next-period productivity scores.  The penultimate hidden state
serves as the **user embedding**.

Architecture
------------
    Input (batch, seq_len, input_size)
        → LSTM (num_layers, hidden_size, dropout)
            → last hidden state  →  user embedding (hidden_size,)
            → linear head        →  productivity forecast (output_size,)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

from app.ml.research_twin import config as _cfg
from app.ml.research_twin.config import (
    LSTM_CFG,
    LSTM_FILENAME,
    LSTMConfig,
    METADATA_FILENAME,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Model definition
# ---------------------------------------------------------------------------

class ProductivityLSTM(nn.Module):
    """
    LSTM that maps temporal feature sequences to:
      • a per-user **embedding** (last hidden state)
      • a **productivity forecast** for the next *output_size* hours
    """

    def __init__(self, cfg: LSTMConfig | None = None):
        super().__init__()
        c = cfg or LSTM_CFG
        self.cfg = c

        self.lstm = nn.LSTM(
            input_size=c.input_size,
            hidden_size=c.hidden_size,
            num_layers=c.num_layers,
            dropout=c.dropout if c.num_layers > 1 else 0.0,
            batch_first=True,
        )

        self.fc = nn.Linear(c.hidden_size, c.output_size)

    def forward(
        self,
        x: torch.Tensor,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Parameters
        ----------
        x : Tensor  shape (batch, seq_len, input_size)

        Returns
        -------
        forecast : Tensor  shape (batch, output_size)  – productivity scores
        embedding : Tensor shape (batch, hidden_size)   – user embedding
        """
        # lstm_out: (batch, seq_len, hidden_size)
        lstm_out, (h_n, _) = self.lstm(x)

        # Use last layer's hidden state as embedding
        embedding = h_n[-1]  # (batch, hidden_size)

        forecast = torch.sigmoid(self.fc(embedding))  # 0–1 productivity

        return forecast, embedding

    def extract_embedding(self, x: torch.Tensor) -> torch.Tensor:
        """Return only the embedding (for inference)."""
        _, emb = self.forward(x)
        return emb


# ---------------------------------------------------------------------------
# Training result
# ---------------------------------------------------------------------------

@dataclass
class LSTMTrainingResult:
    """Output from a training run."""

    epochs_trained: int
    final_loss: float
    best_loss: float
    n_sequences: int
    n_features: int
    history: List[float]  # per-epoch loss

    def to_dict(self) -> Dict[str, Any]:
        return {
            "epochs_trained": self.epochs_trained,
            "final_loss": round(self.final_loss, 6),
            "best_loss": round(self.best_loss, 6),
            "n_sequences": self.n_sequences,
            "n_features": self.n_features,
            "history": [round(x, 6) for x in self.history],
        }


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------

def train_lstm(
    sequences: np.ndarray,
    *,
    targets: np.ndarray | None = None,
    cfg: LSTMConfig | None = None,
    save: bool = True,
) -> Tuple[ProductivityLSTM, LSTMTrainingResult]:
    """
    Train the productivity LSTM on temporal feature sequences.

    Parameters
    ----------
    sequences : ndarray  shape (N, seq_len, n_features)
    targets : ndarray, optional
        shape (N, output_size).  If ``None``, self-supervised:
        the model predicts the mean event-rate of the *last* ``output_size``
        steps of each sequence.
    cfg : LSTMConfig
    save : bool
        Persist model to disk.

    Returns
    -------
    (model, training_result)
    """
    c = cfg or LSTM_CFG
    torch.manual_seed(c.random_state)
    np.random.seed(c.random_state)

    n_seq, seq_len, n_feat = sequences.shape

    # Override input_size from data if needed
    effective_cfg = LSTMConfig(
        input_size=n_feat,
        hidden_size=c.hidden_size,
        num_layers=c.num_layers,
        dropout=c.dropout,
        output_size=c.output_size,
        learning_rate=c.learning_rate,
        epochs=c.epochs,
        batch_size=c.batch_size,
        random_state=c.random_state,
    )

    model = ProductivityLSTM(effective_cfg)

    # Build targets if not provided (self-supervised)
    if targets is None:
        out_size = min(effective_cfg.output_size, seq_len)
        # Target = mean event rates over last out_size steps
        # Only use the first len(FEATURE_CHANNELS) columns (rates, not cyclic)
        from app.ml.research_twin.config import FEATURE_CHANNELS
        n_rate = len(FEATURE_CHANNELS)
        rate_cols = min(n_rate, n_feat)
        # Mean activity across rate channels in last out_size steps
        tail = sequences[:, -out_size:, :rate_cols]  # (N, out_size, rate_cols)
        y = tail.mean(axis=2)  # (N, out_size)
        # Normalise to 0–1
        y_max = y.max() if y.max() > 0 else 1.0
        y = y / y_max
    else:
        y = targets

    X_tensor = torch.from_numpy(sequences).float()
    y_tensor = torch.from_numpy(y).float()

    # Ensure y matches output_size
    if y_tensor.shape[1] != effective_cfg.output_size:
        # Pad or truncate
        if y_tensor.shape[1] < effective_cfg.output_size:
            pad = torch.zeros(
                y_tensor.shape[0],
                effective_cfg.output_size - y_tensor.shape[1],
            )
            y_tensor = torch.cat([y_tensor, pad], dim=1)
        else:
            y_tensor = y_tensor[:, : effective_cfg.output_size]

    dataset = TensorDataset(X_tensor, y_tensor)
    loader = DataLoader(
        dataset,
        batch_size=c.batch_size,
        shuffle=True,
    )

    optimizer = torch.optim.Adam(model.parameters(), lr=c.learning_rate)
    criterion = nn.MSELoss()

    model.train()
    history: List[float] = []
    best_loss = float("inf")

    for epoch in range(c.epochs):
        epoch_loss = 0.0
        n_batches = 0
        for xb, yb in loader:
            optimizer.zero_grad()
            forecast, _ = model(xb)
            loss = criterion(forecast, yb)
            loss.backward()
            optimizer.step()
            epoch_loss += loss.item()
            n_batches += 1

        avg_loss = epoch_loss / max(n_batches, 1)
        history.append(avg_loss)
        best_loss = min(best_loss, avg_loss)

        if (epoch + 1) % max(1, c.epochs // 5) == 0:
            logger.info(
                "Epoch %d/%d – loss %.6f", epoch + 1, c.epochs, avg_loss
            )

    result = LSTMTrainingResult(
        epochs_trained=c.epochs,
        final_loss=history[-1] if history else 0.0,
        best_loss=best_loss,
        n_sequences=n_seq,
        n_features=n_feat,
        history=history,
    )

    if save:
        _save_model(model, result)

    # Update in-memory cache
    global _cached_model
    _cached_model = model

    return model, result


# ---------------------------------------------------------------------------
# Inference helpers
# ---------------------------------------------------------------------------

def predict_productivity(
    sequences: np.ndarray,
    *,
    model: ProductivityLSTM | None = None,
) -> np.ndarray:
    """
    Predict productivity scores for each sequence.

    Returns ndarray shape (N, output_size) with values in [0, 1].
    """
    mdl = model or _load_model()
    mdl.eval()
    with torch.no_grad():
        X = torch.from_numpy(sequences).float()
        forecast, _ = mdl(X)
    return forecast.numpy()


def extract_embeddings(
    sequences: np.ndarray,
    *,
    model: ProductivityLSTM | None = None,
) -> np.ndarray:
    """
    Extract user embeddings from the LSTM hidden state.

    Returns ndarray shape (N, hidden_size).
    """
    mdl = model or _load_model()
    mdl.eval()
    with torch.no_grad():
        X = torch.from_numpy(sequences).float()
        emb = mdl.extract_embedding(X)
    return emb.numpy()


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def _save_model(
    model: ProductivityLSTM,
    result: LSTMTrainingResult,
) -> Path:
    out_dir = _cfg.TWIN_ARTIFACTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    torch.save({
        "state_dict": model.state_dict(),
        "config": {
            "input_size": model.cfg.input_size,
            "hidden_size": model.cfg.hidden_size,
            "num_layers": model.cfg.num_layers,
            "dropout": model.cfg.dropout,
            "output_size": model.cfg.output_size,
        },
    }, out_dir / LSTM_FILENAME)

    meta = result.to_dict()
    (out_dir / METADATA_FILENAME).write_text(json.dumps(meta, indent=2))

    logger.info("Saved LSTM model to %s", out_dir)
    return out_dir


_cached_model: Optional[ProductivityLSTM] = None


def _load_model() -> ProductivityLSTM:
    global _cached_model
    if _cached_model is not None:
        return _cached_model

    d = _cfg.TWIN_ARTIFACTS_DIR
    path = d / LSTM_FILENAME
    if not path.exists():
        raise RuntimeError(
            "No trained LSTM model found. Call train_lstm() first."
        )

    checkpoint = torch.load(path, map_location="cpu", weights_only=False)
    cfg_dict = checkpoint["config"]
    cfg = LSTMConfig(
        input_size=cfg_dict["input_size"],
        hidden_size=cfg_dict["hidden_size"],
        num_layers=cfg_dict["num_layers"],
        dropout=cfg_dict["dropout"],
        output_size=cfg_dict["output_size"],
    )
    model = ProductivityLSTM(cfg)
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()

    _cached_model = model
    return _cached_model


def reload_model() -> None:
    """Clear the cached model (forces reload on next use)."""
    global _cached_model
    _cached_model = None
