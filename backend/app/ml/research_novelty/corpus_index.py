"""
FAISS-backed corpus index for fast nearest-neighbour search over field
embeddings.

Supports:
  * **Flat** (exact) index for small corpora.
  * **IVFFlat** for corpora with 10 K–100 K+ documents.
  * Persisting / loading the index + metadata from disk.

Usage::

    from app.ml.research_novelty.corpus_index import CorpusIndex

    idx = CorpusIndex(dimension=768)
    idx.add(embeddings, ids=paper_ids)
    distances, neighbours = idx.search(query_vec, k=10)
    idx.save("/path/to/index")

    idx2 = CorpusIndex.load("/path/to/index")
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import faiss
import numpy as np

from app.ml.research_novelty.config import (
    CONFIG,
    FAISS_INDEX_TYPE,
    FAISS_NLIST,
    FAISS_NPROBE,
    NOVELTY_ARTIFACTS_DIR,
)

logger = logging.getLogger(__name__)

# File names inside the index directory
_INDEX_FILE = "faiss.index"
_META_FILE = "index_meta.json"


@dataclass
class CorpusIndex:
    """
    Manages a FAISS index of field-corpus embeddings.

    Parameters
    ----------
    dimension : int
        Embedding dimensionality (768 for SciBERT).
    index_type : str
        ``"Flat"`` or ``"IVFFlat"``.
    nlist : int
        Number of Voronoi cells for IVF indices.
    nprobe : int
        Number of cells to visit at search time (higher → more accurate).
    """

    dimension: int = 768
    index_type: str = FAISS_INDEX_TYPE
    nlist: int = FAISS_NLIST
    nprobe: int = FAISS_NPROBE

    # Internal state (not passed at construction)
    _index: Optional[faiss.Index] = field(default=None, init=False, repr=False)
    _id_map: Dict[int, str] = field(default_factory=dict, init=False, repr=False)
    _centroid: Optional[np.ndarray] = field(default=None, init=False, repr=False)
    _n_vectors: int = field(default=0, init=False, repr=False)
    _trained: bool = field(default=False, init=False, repr=False)

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------

    def _build_index(self) -> faiss.Index:
        """Build a fresh FAISS index based on ``index_type``."""
        if self.index_type == "Flat":
            index = faiss.IndexFlatL2(self.dimension)
        elif self.index_type == "IVFFlat":
            quantiser = faiss.IndexFlatL2(self.dimension)
            index = faiss.IndexIVFFlat(quantiser, self.dimension, self.nlist)
            index.nprobe = self.nprobe
        else:
            raise ValueError(f"Unsupported FAISS index type: {self.index_type}")
        return index

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add(
        self,
        embeddings: np.ndarray,
        *,
        ids: Optional[List[str]] = None,
    ) -> None:
        """
        Add vectors to the index.

        Parameters
        ----------
        embeddings : np.ndarray
            Shape ``(n, dimension)``, float32.
        ids : list[str], optional
            String identifiers for each vector.  If omitted, sequential
            integers are used.
        """
        embeddings = np.ascontiguousarray(embeddings, dtype=np.float32)
        n = embeddings.shape[0]
        if embeddings.shape[1] != self.dimension:
            raise ValueError(
                f"Expected dimension {self.dimension}, got {embeddings.shape[1]}"
            )

        if self._index is None:
            self._index = self._build_index()

        # IVFFlat requires training before adding
        needs_training = (
            self.index_type == "IVFFlat"
            and not self._trained
        )
        if needs_training:
            if n < self.nlist:
                # Fall back to Flat if corpus is too small for IVF
                logger.warning(
                    "Corpus size %d < nlist %d – falling back to Flat index",
                    n, self.nlist
                )
                self._index = faiss.IndexFlatL2(self.dimension)
                self.index_type = "Flat"
            else:
                self._index.train(embeddings)
                self._trained = True

        self._index.add(embeddings)

        # Track IDs
        offset = self._n_vectors
        if ids is not None:
            for i, paper_id in enumerate(ids):
                self._id_map[offset + i] = paper_id
        else:
            for i in range(n):
                self._id_map[offset + i] = str(offset + i)

        self._n_vectors += n

        # Recompute centroid incrementally
        if self._centroid is None:
            self._centroid = embeddings.mean(axis=0)
        else:
            old_total = self._centroid * (self._n_vectors - n)
            new_total = old_total + embeddings.sum(axis=0)
            self._centroid = new_total / self._n_vectors

        logger.info(
            "Added %d vectors → total %d (index_type=%s)",
            n, self._n_vectors, self.index_type,
        )

    def search(
        self,
        query: np.ndarray,
        k: int = CONFIG.knn_k,
    ) -> Tuple[np.ndarray, np.ndarray, List[str]]:
        """
        Find the *k* nearest neighbours.

        Parameters
        ----------
        query : np.ndarray
            Shape ``(1, dimension)`` or ``(dimension,)``.
        k : int
            Number of neighbours.

        Returns
        -------
        distances : np.ndarray  shape (1, k)
        indices   : np.ndarray  shape (1, k)
        ids       : list[str]   neighbour paper IDs
        """
        if self._index is None or self._n_vectors == 0:
            raise RuntimeError("Index is empty – call add() first.")

        query = np.ascontiguousarray(
            query.reshape(1, -1), dtype=np.float32
        )
        k = min(k, self._n_vectors)
        distances, indices = self._index.search(query, k)

        result_ids = [
            self._id_map.get(int(idx), str(idx))
            for idx in indices[0]
        ]
        return distances, indices, result_ids

    @property
    def centroid(self) -> np.ndarray:
        """Mean embedding (field centroid)."""
        if self._centroid is None:
            raise RuntimeError("Index is empty – no centroid available.")
        return self._centroid.copy()

    @property
    def size(self) -> int:
        return self._n_vectors

    def centroid_distance(self, query: np.ndarray) -> float:
        """
        Euclidean distance between *query* and the corpus centroid.

        Parameters
        ----------
        query : np.ndarray
            Shape ``(dimension,)`` or ``(1, dimension)``.

        Returns
        -------
        float
        """
        q = query.flatten().astype(np.float32)
        c = self.centroid.flatten().astype(np.float32)
        return float(np.linalg.norm(q - c))

    def mean_knn_distance(
        self, query: np.ndarray, k: int = CONFIG.knn_k
    ) -> float:
        """
        Mean L2 distance to the *k* nearest neighbours.

        Provides a **local** novelty signal (distance from the dense region
        of the field) as opposed to the global centroid distance.
        """
        distances, _, _ = self.search(query, k=k)
        return float(np.mean(distances[0]))

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, directory: Optional[Path] = None) -> Path:
        """Write the FAISS index + metadata to *directory*."""
        directory = Path(directory or NOVELTY_ARTIFACTS_DIR / "index")
        directory.mkdir(parents=True, exist_ok=True)

        faiss.write_index(self._index, str(directory / _INDEX_FILE))

        meta = {
            "dimension": self.dimension,
            "index_type": self.index_type,
            "nlist": self.nlist,
            "nprobe": self.nprobe,
            "n_vectors": self._n_vectors,
            "id_map": {str(k): v for k, v in self._id_map.items()},
            "centroid": self._centroid.tolist() if self._centroid is not None else None,
        }
        (directory / _META_FILE).write_text(json.dumps(meta, indent=2))

        logger.info("Saved FAISS index to %s (%d vectors)", directory, self._n_vectors)
        return directory

    @classmethod
    def load(cls, directory: Optional[Path] = None) -> "CorpusIndex":
        """Load a previously-saved index."""
        directory = Path(directory or NOVELTY_ARTIFACTS_DIR / "index")
        index_path = directory / _INDEX_FILE
        meta_path = directory / _META_FILE

        if not index_path.exists():
            raise FileNotFoundError(f"No FAISS index at {index_path}")

        with open(meta_path) as f:
            meta = json.load(f)

        obj = cls(
            dimension=meta["dimension"],
            index_type=meta["index_type"],
            nlist=meta["nlist"],
            nprobe=meta["nprobe"],
        )
        obj._index = faiss.read_index(str(index_path))
        obj._n_vectors = meta["n_vectors"]
        obj._id_map = {int(k): v for k, v in meta["id_map"].items()}
        if meta.get("centroid") is not None:
            obj._centroid = np.array(meta["centroid"], dtype=np.float32)
        obj._trained = True

        logger.info("Loaded FAISS index from %s (%d vectors)", directory, obj._n_vectors)
        return obj

    @classmethod
    def from_embeddings(
        cls,
        embeddings: np.ndarray,
        *,
        ids: Optional[List[str]] = None,
        dimension: Optional[int] = None,
        index_type: str = FAISS_INDEX_TYPE,
        nlist: int = FAISS_NLIST,
        nprobe: int = FAISS_NPROBE,
    ) -> "CorpusIndex":
        """Convenience constructor: build index from a matrix."""
        dim = dimension or embeddings.shape[1]
        idx = cls(dimension=dim, index_type=index_type, nlist=nlist, nprobe=nprobe)
        idx.add(embeddings, ids=ids)
        return idx
