"""
Collaboration Network Intelligence module.

Analyses citation and co-authorship graphs to quantify research
collaboration strength, detect isolation risk, identify community
structure (Louvain), and suggest new collaborators by finding
network gaps (high citation, no collaboration).

Submodules
----------
config       – tunables, thresholds, scoring weights
graph        – NetworkX graph construction from edge lists
metrics      – PageRank, betweenness centrality, clustering coefficient
communities  – Louvain community detection
gaps         – network-gap identification (cited-but-not-collaborated)
scorer       – orchestration layer producing final scores
service      – public entry-point for the API layer
"""
