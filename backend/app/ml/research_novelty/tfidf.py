"""
TF-IDF terminology uniqueness scorer.

Fits a TF-IDF vectoriser on the field corpus, then scores a query document
by measuring how much of its vocabulary concentrates on **rare** terms –
i.e. terms with low document frequency in the corpus.

The output is a *terminology uniqueness index* (0–100) that complements
the embedding-distance signal for novelty scoring.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from app.ml.research_novelty.config import (
    TFIDF_MAX_FEATURES,
    TFIDF_NGRAM_MAX,
    TFIDF_NGRAM_MIN,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TfidfResult:
    """Output of the TF-IDF terminology analysis."""

    # 0–100: higher = more unique vocabulary relative to the field
    terminology_uniqueness_index: float
    # Mean TF-IDF weight of the query document's terms
    mean_tfidf_weight: float
    # Top-N rarest terms (by IDF) found in the query
    top_rare_terms: List[Tuple[str, float]]
    # Fraction of query terms absent from the corpus vocabulary
    oov_ratio: float
    # Total unique terms in the query (after vectoriser processing)
    n_query_terms: int


# ---------------------------------------------------------------------------
# Vectoriser wrapper
# ---------------------------------------------------------------------------

class TerminologyScorer:
    """
    Fits a TF-IDF model on the corpus and scores query documents.

    Parameters
    ----------
    max_features : int
        Maximum vocabulary size.
    ngram_range : tuple[int, int]
        N-gram range for the vectoriser.
    """

    def __init__(
        self,
        max_features: int = TFIDF_MAX_FEATURES,
        ngram_range: Tuple[int, int] = (TFIDF_NGRAM_MIN, TFIDF_NGRAM_MAX),
    ):
        self._vectoriser = TfidfVectorizer(
            max_features=max_features,
            ngram_range=ngram_range,
            sublinear_tf=True,
            stop_words="english",
        )
        self._fitted = False
        self._idf: Optional[np.ndarray] = None
        self._vocab: Optional[Dict[str, int]] = None

    # ------------------------------------------------------------------
    # Fit on corpus
    # ------------------------------------------------------------------

    def fit(self, corpus: List[str]) -> "TerminologyScorer":
        """
        Learn TF-IDF statistics from the field corpus.

        Parameters
        ----------
        corpus : list[str]
            One string per corpus document.
        """
        self._vectoriser.fit(corpus)
        self._idf = self._vectoriser.idf_
        self._vocab = self._vectoriser.vocabulary_
        self._fitted = True
        logger.info(
            "TF-IDF fitted on %d documents, vocab size = %d",
            len(corpus),
            len(self._vocab),
        )
        return self

    # ------------------------------------------------------------------
    # Score a query document
    # ------------------------------------------------------------------

    def score(
        self,
        text: str,
        *,
        top_n: int = 20,
        scale: float = 100.0,
    ) -> TfidfResult:
        """
        Compute terminology uniqueness for *text* against the fitted corpus.

        The uniqueness index is driven by **how much of the query's weight
        falls on high-IDF (rare) terms**.  A document that uses mostly
        common field jargon will have a low score; one that introduces novel
        terminology will score higher.

        Parameters
        ----------
        text : str
            Full manuscript text.
        top_n : int
            Number of rarest terms to return.
        scale : float
            Maximum score (default 100).

        Returns
        -------
        TfidfResult
        """
        if not self._fitted:
            raise RuntimeError("TerminologyScorer not fitted – call fit() first.")

        # Transform the query
        query_vec = self._vectoriser.transform([text])
        query_arr = query_vec.toarray().flatten()  # shape (vocab_size,)

        # Non-zero entries correspond to terms present in the query
        nonzero_mask = query_arr > 0
        n_query_terms = int(nonzero_mask.sum())

        if n_query_terms == 0:
            return TfidfResult(
                terminology_uniqueness_index=0.0,
                mean_tfidf_weight=0.0,
                top_rare_terms=[],
                oov_ratio=1.0,
                n_query_terms=0,
            )

        # ---- Mean TF-IDF weight (measures overall vocabulary rarity) -----
        mean_weight = float(query_arr[nonzero_mask].mean())

        # ---- IDF-based uniqueness ----------------------------------------
        # For the query's non-zero terms, gather their IDF values.
        query_idfs = self._idf[nonzero_mask]
        max_idf = float(self._idf.max()) if self._idf.max() > 0 else 1.0

        # Weighted average: terms with higher TF-IDF contribute more
        weighted_idf = float(
            np.average(query_idfs, weights=query_arr[nonzero_mask])
        )
        # Normalise to [0, 1] using the max IDF seen in corpus
        normalised_uniqueness = min(1.0, weighted_idf / max_idf)

        # ---- OOV ratio (terms the corpus never saw) ----------------------
        # Tokenise the query the same way the vectoriser does
        analyser = self._vectoriser.build_analyzer()
        query_tokens = set(analyser(text))
        if len(query_tokens) == 0:
            oov_ratio = 0.0
        else:
            in_vocab = sum(1 for t in query_tokens if t in self._vocab)
            oov_ratio = 1.0 - (in_vocab / len(query_tokens))

        # Blend: normalised IDF uniqueness (70%) + OOV ratio boost (30%)
        raw_score = 0.70 * normalised_uniqueness + 0.30 * oov_ratio
        uniqueness_index = scale * min(1.0, raw_score)

        # ---- Top rare terms -----------------------------------------------
        feature_names = self._vectoriser.get_feature_names_out()
        term_idf_pairs = [
            (feature_names[i], float(self._idf[i]))
            for i in np.where(nonzero_mask)[0]
        ]
        term_idf_pairs.sort(key=lambda x: x[1], reverse=True)
        top_rare = term_idf_pairs[:top_n]

        return TfidfResult(
            terminology_uniqueness_index=round(uniqueness_index, 2),
            mean_tfidf_weight=round(mean_weight, 4),
            top_rare_terms=[(t, round(v, 4)) for t, v in top_rare],
            oov_ratio=round(oov_ratio, 4),
            n_query_terms=n_query_terms,
        )
