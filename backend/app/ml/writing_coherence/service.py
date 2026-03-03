"""
Writing Coherence Service – public entry-point for the API layer.

Provides:
  * ``score_document_text()`` – score raw text
  * ``score_document_by_id()`` – fetch a ``DocumentArtifact`` and score it

Follows the same service-layer patterns used elsewhere in the backend.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.ml.writing_coherence.config import CONFIG, CoherenceConfig
from app.ml.writing_coherence.scorer import (
    WritingCoherenceScore,
    score_text,
    segment_paragraphs,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Score from raw text
# ---------------------------------------------------------------------------

def score_document_text(
    text: str,
    *,
    paragraphs: Optional[List[str]] = None,
    config: Optional[CoherenceConfig] = None,
) -> Dict[str, Any]:
    """
    Analyse writing coherence of *text* and return a JSON-ready dict.

    Parameters
    ----------
    text : str
        Full document text.
    paragraphs : list[str], optional
        Pre-segmented paragraphs.  Auto-segmented if omitted.
    config : CoherenceConfig, optional
        Override default tunables.

    Returns
    -------
    dict with keys ``coherence_score``, ``topic_drift_score``,
    ``structural_consistency_score``, ``composite_score``, and detail sections.
    """
    result: WritingCoherenceScore = score_text(
        text, paragraphs=paragraphs, config=config,
    )
    return result.to_dict()


# ---------------------------------------------------------------------------
# Score from a DocumentArtifact ID (DB-backed)
# ---------------------------------------------------------------------------

def score_document_by_id(
    document_id: str,
    db,
    *,
    config: Optional[CoherenceConfig] = None,
) -> Dict[str, Any]:
    """
    Fetch a ``DocumentArtifact`` by *document_id*, extract its normalised text,
    and score coherence.

    Parameters
    ----------
    document_id : str | UUID
        Primary key of the document in ``document_artifacts``.
    db : sqlalchemy.orm.Session
        Active database session.
    config : CoherenceConfig, optional
        Override default tunables.

    Returns
    -------
    dict  – same shape as ``score_document_text()``.

    Raises
    ------
    ValueError
        If the document does not exist or has no extracted text.
    """
    from app.services.document_service import DocumentService

    doc_svc = DocumentService(db)
    document = doc_svc.get_document(document_id)

    if document is None:
        raise ValueError(f"Document '{document_id}' not found.")

    text: Optional[str] = document.document_text or document.raw_text
    if not text or not text.strip():
        raise ValueError(
            f"Document '{document_id}' has no extracted text to analyse."
        )

    return score_document_text(text, config=config)
