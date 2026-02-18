# App Layer Boundaries

Quick reference for the four-layer architecture. Full detail: [../ARCHITECTURE.md](../ARCHITECTURE.md).

| Layer | Purpose | Key packages |
|-------|---------|--------------|
| **Experience** | API, RBAC, response shape | `api/v1/endpoints/`, `core/security.py`, `core/data_visibility.py` |
| **Intelligence** | Signals with evidence + explanation | `core/interpretability.py`, `services/engagement_engine.py`, `services/intelligence_signals_service.py`, timeline feedback (suggestion generation) |
| **Event normalization** | Taxonomy, append-only event store, state machines | `core/event_taxonomy.py`, `core/state_machines.py`, `services/event_store.py`, `services/state_transition_service.py`, `models/longitudinal_event.py` |
| **Input** | User/system inputs, domain writes, event emission | `services/document_service.py`, `services/questionnaire_draft_service.py`, `services/progress_service.py`, `services/stage_suggestion_service.py`, `services/timeline_feedback_service.py`, orchestrators |

**Rules**

- All signals: traceable to raw events (evidence includes `contributing_event_ids`).
- No signal without evidence and explanation (interpretability layer).
- Event store: append-only; no update/delete.
- No document content or raw questionnaire answers in event store or admin analytics.
