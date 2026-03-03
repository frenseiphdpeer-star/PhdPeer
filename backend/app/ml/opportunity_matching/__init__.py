"""
Opportunity Matching Engine
===========================

Matches researchers with opportunities (grants, conferences, collaborations)
using semantic similarity, a LightGBM learning-to-rank model trained on
historical acceptance outcomes, and a time-to-deadline urgency factor.

Modules
-------
config          – tunables, feature catalogue, paths
embeddings      – sentence-transformers wrapper (reuses writing-coherence embedder)
features        – feature engineering pipeline (cosine sim, stage one-hot, …)
model           – LightGBM ranking + success-probability calibration
recommender     – preparation-recommendation generation
scorer          – orchestration layer combining all components
service         – public API consumed by the endpoint layer
"""
