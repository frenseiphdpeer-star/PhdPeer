"""
User embedding extraction & analysis for the AI Research Twin.

Takes the LSTM hidden-state embeddings and provides:
  • Per-user embedding vectors (for similarity / recommendation)
  • Embedding-space clustering (productivity archetypes)
  • Embedding-based similarity search between researchers
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from app.ml.research_twin.config import EMBED_CFG, EmbeddingConfig

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Containers
# ---------------------------------------------------------------------------

@dataclass
class UserEmbedding:
    """Embedding vector for a single researcher."""

    researcher_id: str
    vector: np.ndarray           # shape (embedding_dim,)
    norm: float                  # L2 norm

    def to_dict(self) -> Dict[str, Any]:
        return {
            "researcher_id": self.researcher_id,
            "vector": self.vector.tolist(),
            "norm": round(float(self.norm), 6),
            "dim": len(self.vector),
        }


@dataclass
class EmbeddingAnalysis:
    """Aggregated embedding-space analysis."""

    embeddings: List[UserEmbedding]
    mean_vector: np.ndarray
    similarity_matrix: np.ndarray  # (n_users, n_users) cosine similarity

    def to_dict(self) -> Dict[str, Any]:
        return {
            "n_users": len(self.embeddings),
            "embedding_dim": len(self.mean_vector),
            "embeddings": [e.to_dict() for e in self.embeddings],
            "similarity_matrix": self.similarity_matrix.tolist(),
        }


# ---------------------------------------------------------------------------
# Embedding helpers
# ---------------------------------------------------------------------------

def build_user_embedding(
    researcher_id: str,
    raw_embeddings: np.ndarray,
    *,
    cfg: EmbeddingConfig | None = None,
) -> UserEmbedding:
    """
    Aggregate multiple sequence embeddings into a single user embedding.

    Parameters
    ----------
    researcher_id : str
    raw_embeddings : ndarray  shape (N, hidden_size)
        Multiple embeddings (one per sequence) for the same user.
    cfg : EmbeddingConfig

    Returns
    -------
    UserEmbedding  with mean-pooled vector.
    """
    c = cfg or EMBED_CFG

    # Mean-pool across sequences
    vec = raw_embeddings.mean(axis=0).astype(np.float64)

    # Optional PCA reduction
    if c.pca_components > 0 and c.pca_components < len(vec):
        # Simple truncation (acts like PCA when embeddings are already
        # ordered by variance — full PCA requires multiple users)
        vec = vec[: c.pca_components]

    norm = float(np.linalg.norm(vec))

    return UserEmbedding(
        researcher_id=researcher_id,
        vector=vec,
        norm=norm,
    )


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two vectors."""
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def compute_similarity_matrix(
    embeddings: List[UserEmbedding],
) -> np.ndarray:
    """
    Pair-wise cosine similarity matrix.

    Returns ndarray shape (n_users, n_users).
    """
    n = len(embeddings)
    mat = np.zeros((n, n), dtype=np.float64)
    for i in range(n):
        for j in range(i, n):
            sim = cosine_similarity(embeddings[i].vector, embeddings[j].vector)
            mat[i, j] = sim
            mat[j, i] = sim
    return mat


def analyse_embeddings(
    user_embeddings: List[UserEmbedding],
) -> EmbeddingAnalysis:
    """
    Produce an embedding-space analysis across multiple researchers.
    """
    if not user_embeddings:
        return EmbeddingAnalysis(
            embeddings=[],
            mean_vector=np.array([]),
            similarity_matrix=np.array([]).reshape(0, 0),
        )

    vecs = np.array([e.vector for e in user_embeddings])
    mean_vec = vecs.mean(axis=0)
    sim_mat = compute_similarity_matrix(user_embeddings)

    return EmbeddingAnalysis(
        embeddings=user_embeddings,
        mean_vector=mean_vec,
        similarity_matrix=sim_mat,
    )


def find_similar_users(
    target: UserEmbedding,
    candidates: List[UserEmbedding],
    *,
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """
    Find the *top_k* most similar researchers to *target*.
    """
    scored = []
    for cand in candidates:
        if cand.researcher_id == target.researcher_id:
            continue
        sim = cosine_similarity(target.vector, cand.vector)
        scored.append({
            "researcher_id": cand.researcher_id,
            "similarity": round(sim, 4),
        })
    scored.sort(key=lambda x: x["similarity"], reverse=True)
    return scored[:top_k]
