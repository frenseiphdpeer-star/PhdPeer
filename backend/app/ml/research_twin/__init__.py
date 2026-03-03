"""
AI Research Twin – Behavioral Modeling System
==============================================

Models individual researcher productivity cycles from five behavioural
signals (writing timestamps, revision density, opportunity engagement
timing, submission behaviour, supervision interaction timing) to
produce:

* **productive_time_window** – peak-hours / peak-days estimate
* **procrastination_pattern** – detected delay patterns
* **optimal_submission_window** – best time-of-week to submit
* **personalized_nudge_recommendations** – actionable nudges

Architecture
------------
config.py       – tunables, input signal catalogue, LSTM hyper-params
temporal.py     – raw event → temporal feature vectors (hourly / daily)
lstm.py         – PyTorch LSTM for productivity-cycle modelling
embedding.py    – user embedding extraction from LSTM hidden state
recommender.py  – embedding → personalised recommendations / nudges
scorer.py       – orchestration pipeline
service.py      – public API + synthetic data helper
"""
