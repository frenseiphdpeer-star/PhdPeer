"""
Publisher Readiness Index scoring module.

Predicts how ready a researcher's work is for journal submission by
combining six input signals into a 0–100 readiness score with
categorical labels and confidence estimates.

Sub-modules
-----------
config      – tunables, feature catalogue, thresholds, paths
features    – normalisation & derived-feature engineering
model       – LightGBM regression + quantile confidence
scorer      – orchestration pipeline
service     – public API consumed by REST endpoints
"""
