"""
Research Novelty Service – public entry-point for the API layer.

Manages the lifecycle of the corpus index and TF-IDF model, and
exposes high-level functions for scoring manuscripts.

Provides:
  * ``score_text()``          – score raw text against the corpus
  * ``build_corpus_index()``  – build / replace the FAISS index
  * ``get_corpus_status()``   – report index metadata
  * ``generate_demo_corpus()``– create a small synthetic corpus for testing
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from app.ml.research_novelty.config import CONFIG, NOVELTY_ARTIFACTS_DIR, NoveltyConfig
from app.ml.research_novelty.corpus_index import CorpusIndex
from app.ml.research_novelty.scorer import NoveltyScore, score_manuscript
from app.ml.research_novelty.tfidf import TerminologyScorer

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level cached state
# ---------------------------------------------------------------------------
_cached_index: Optional[CorpusIndex] = None
_cached_tfidf: Optional[TerminologyScorer] = None


def _get_index() -> CorpusIndex:
    """Return the cached FAISS index, loading from disk if needed."""
    global _cached_index
    if _cached_index is None:
        index_dir = NOVELTY_ARTIFACTS_DIR / "index"
        if index_dir.exists():
            _cached_index = CorpusIndex.load(index_dir)
        else:
            raise RuntimeError(
                "No corpus index available.  Call build_corpus_index() first."
            )
    return _cached_index


def _get_tfidf() -> TerminologyScorer:
    """Return the cached TF-IDF scorer."""
    global _cached_tfidf
    if _cached_tfidf is None:
        raise RuntimeError(
            "TF-IDF scorer not available.  Call build_corpus_index() first."
        )
    return _cached_tfidf


def reload() -> None:
    """Force-reload the corpus index and TF-IDF scorer."""
    global _cached_index, _cached_tfidf
    _cached_index = None
    _cached_tfidf = None


# ---------------------------------------------------------------------------
# Score text
# ---------------------------------------------------------------------------

def score_text(
    text: str,
    *,
    citations: Optional[List[str]] = None,
    config: Optional[NoveltyConfig] = None,
    _embedder=None,
    _index: Optional[CorpusIndex] = None,
    _tfidf: Optional[TerminologyScorer] = None,
) -> Dict[str, Any]:
    """
    Score the novelty of *text* against the field corpus.

    Parameters
    ----------
    text : str
        Full manuscript text.
    citations : list[str], optional
        Citation identifiers.
    config : NoveltyConfig, optional
        Override default scoring weights.

    Returns
    -------
    dict
        JSON-serialisable result with keys ``novelty_score``,
        ``field_distance``, ``terminology_uniqueness_index``, etc.
    """
    # Allow dependency injection for testing
    if _embedder is None:
        from app.ml.research_novelty.embeddings import get_embedder
        _embedder = get_embedder()

    index = _index or _get_index()
    tfidf = _tfidf or _get_tfidf()

    embedding = _embedder.encode(text)  # shape (1, dim)
    result: NoveltyScore = score_manuscript(
        embedding,
        index,
        tfidf,
        text,
        citations=citations,
        config=config,
    )
    return result.to_dict()


# ---------------------------------------------------------------------------
# Build / manage corpus index
# ---------------------------------------------------------------------------

def build_corpus_index(
    texts: List[str],
    *,
    ids: Optional[List[str]] = None,
    save: bool = True,
    _embedder=None,
) -> Dict[str, Any]:
    """
    Build the FAISS index and fit the TF-IDF vectoriser from *texts*.

    Parameters
    ----------
    texts : list[str]
        One document per element (the field corpus).
    ids : list[str], optional
        Paper identifiers (DOIs, keys, etc.).
    save : bool
        Persist to disk (default ``True``).

    Returns
    -------
    dict with ``corpus_size``, ``dimension``, ``index_type``.
    """
    global _cached_index, _cached_tfidf

    if _embedder is None:
        from app.ml.research_novelty.embeddings import get_embedder
        _embedder = get_embedder()

    logger.info("Embedding %d corpus documents…", len(texts))
    embeddings = _embedder.encode(texts)

    index = CorpusIndex.from_embeddings(
        embeddings,
        ids=ids,
        dimension=_embedder.dimension,
    )

    tfidf = TerminologyScorer()
    tfidf.fit(texts)

    if save:
        index.save()

    _cached_index = index
    _cached_tfidf = tfidf

    return {
        "corpus_size": index.size,
        "dimension": _embedder.dimension,
        "index_type": index.index_type,
    }


def get_corpus_status() -> Dict[str, Any]:
    """Return metadata about the current corpus index."""
    global _cached_index
    try:
        index = _get_index()
        return {
            "loaded": True,
            "corpus_size": index.size,
            "dimension": index.dimension,
            "index_type": index.index_type,
        }
    except RuntimeError:
        return {
            "loaded": False,
            "corpus_size": 0,
            "dimension": 0,
            "index_type": "none",
        }


# ---------------------------------------------------------------------------
# Demo / synthetic corpus
# ---------------------------------------------------------------------------

def generate_demo_corpus(n: int = 50) -> List[str]:
    """
    Return *n* synthetic 'papers' for testing.

    Each paper is a few sentences from a randomly-picked topic.
    """
    import random

    topics = [
        (
            "deep learning",
            [
                "We propose a novel architecture based on transformer layers for image classification.",
                "Our model leverages self-attention mechanisms to capture long-range dependencies.",
                "Experiments on ImageNet demonstrate state-of-the-art accuracy with fewer parameters.",
                "We introduce a new regularisation technique that improves generalisation.",
                "The training procedure uses mixed-precision arithmetic for efficiency.",
            ],
        ),
        (
            "genomics",
            [
                "We present a genome-wide association study identifying novel risk loci.",
                "Our analysis of whole-exome sequencing data reveals rare variants.",
                "The bioinformatics pipeline employs GATK for variant calling.",
                "We investigate the role of non-coding RNA in gene regulation.",
                "Population stratification was controlled using principal components.",
            ],
        ),
        (
            "climate science",
            [
                "We model the impact of aerosol emissions on global temperature.",
                "Satellite observations are combined with reanalysis datasets.",
                "Our simulations project a 2.5°C increase by 2100 under RCP 8.5.",
                "We quantify the carbon sequestration potential of mangrove forests.",
                "Ice core data provide a proxy for historical CO2 concentrations.",
            ],
        ),
        (
            "economics",
            [
                "We estimate the causal effect of minimum wage increases on employment.",
                "Our instrumental-variable approach addresses endogeneity concerns.",
                "Panel data from 50 US states over 20 years forms the sample.",
                "The regression-discontinuity design exploits policy thresholds.",
                "Robustness checks with alternative specifications confirm the findings.",
            ],
        ),
    ]

    rng = random.Random(42)
    papers = []
    for _ in range(n):
        topic_name, sentences = rng.choice(topics)
        k = rng.randint(2, len(sentences))
        paper = " ".join(rng.sample(sentences, k))
        papers.append(paper)
    return papers
