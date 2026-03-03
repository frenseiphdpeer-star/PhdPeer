"""
Dropout Risk Prediction module.

Binary classification system that predicts PhD student dropout risk by:

1. Engineering slope/trend features from longitudinal signals.
2. Training a **Logistic Regression** baseline and an **XGBoost** classifier.
3. Evaluating via AUC-ROC and precision-recall metrics.
4. Explaining predictions with **SHAP** feature attributions.

Designed for **early warning** — flags at-risk students 8–12 weeks before
a potential dropout event.
"""
