"""
Research Novelty Scoring module.

Computes a novelty score (0–100) for a research manuscript by:

1. Generating a **SciBERT** embedding of the manuscript text.
2. Comparing that embedding against a pre-indexed **field corpus** via FAISS.
3. Computing the embedding distance from the field centroid.
4. Weighting rare terminology via **TF-IDF**.
5. Combining distance and terminology uniqueness into a composite score.

Designed to scale to 100 K+ corpus documents using FAISS approximate
nearest-neighbour search.
"""
