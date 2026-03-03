"""
Cross-Feature Intelligence Fusion Engine.

Identifies correlations and predictive relationships across all
PhdPeer intelligence signals:

  * Supervision latency
  * Writing coherence improvement
  * Health score trajectory
  * Opportunity engagement
  * Network centrality
  * Publication acceptance

Submodules
----------
config     – signal catalogue, lag parameters, model hyper-parameters
signals    – temporal alignment and normalisation of cross-module signals
features   – lag feature engineering, correlation matrix computation
model      – multi-target LightGBM regression with feature importance
insights   – automated insight generation from correlations & importances
scorer     – orchestration layer producing final fusion analysis
service    – public entry-point for the API layer
"""
