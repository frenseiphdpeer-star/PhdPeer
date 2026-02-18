# System Architecture

This document describes the refactored system architecture: role-based access control, standardized event taxonomy, immutable event store, and strict separation of layers. **All signals are traceable to raw events; no signal exists without evidence and explanation.**

---

## Table of Contents

1. [Layer Separation](#layer-separation)
2. [Cross-Cutting Concerns](#cross-cutting-concerns)
3. [Data Flow and Traceability](#data-flow-and-traceability)
4. [Module Map by Layer](#module-map-by-layer)
5. [Principles](#principles)

---

## Layer Separation

The system enforces strict separation between four layers. Upper layers depend only on lower layers; the event store is the single source of truth for all user actions and system events.

```
┌─────────────────────────────────────────────────────────────────┐
│  EXPERIENCE LAYER                                                │
│  API endpoints, RBAC enforcement, response shaping               │
│  Consumes: intelligence outputs, event store (read), state      │
└─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│  INTELLIGENCE LAYER                                              │
│  Signals, interpretability, engagement, timeline feedback       │
│  Consumes: event store (read-only), normalized events only       │
│  Outputs: InterpretableSignal (evidence + explanation + value)   │
└─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│  EVENT NORMALIZATION LAYER                                       │
│  Event taxonomy, event store (append-only), state transitions    │
│  Consumes: input layer outcomes (entity IDs, no raw content)      │
│  Outputs: LongitudinalEvent records only                         │
└─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│  INPUT LAYER                                                     │
│  Document upload, questionnaire submission, progress log,        │
│  stage accept/override, opportunity/supervision/milestone ops    │
│  Outputs: domain entities + emission of normalized events        │
└─────────────────────────────────────────────────────────────────┘
```

### 1. Input Layer

- **Responsibility**: Accept user and system inputs; create/update domain entities; **emit standardized events only** (no ad-hoc logging).
- **Components**: Document upload (DocumentService), questionnaire submission (QuestionnaireDraftService), progress/milestone (ProgressService), stage classification accept/override (StageSuggestionService), opportunity/supervision/milestone/writing state transitions (StateTransitionService), timeline feedback accept/reject (TimelineFeedbackService).
- **Rules**: Never expose document content or raw questionnaire answers to upper layers. Emit events via Event Store only; use Event Taxonomy for `event_type` and `source_module`.

### 2. Event Normalization Layer

- **Responsibility**: Single taxonomy for all event types; immutable, append-only longitudinal event store; state machine transitions with transition logging.
- **Components**: `core/event_taxonomy.py` (EventType, SUPPORTED_EVENT_TYPES), `services/event_store.py` (EventStore, emit_event), `models/longitudinal_event.py`, `core/state_machines.py`, `services/state_transition_service.py`.
- **Rules**: No update/delete on longitudinal events. All state changes for Opportunity, SupervisionSession, Milestone, WritingVersion go through state transition service and log a `state_transition` event.

### 3. Intelligence Layer

- **Responsibility**: Derive signals from the event store and domain aggregates; attach **evidence** (contributing event_ids, time window) and **explanation** to every signal; no signal without interpretability payload.
- **Components**: Engagement engine (inactivity rules, monthly digest), intelligence signals service (continuity_index, dropout_risk_signal, supervisor_engagement_alert, opportunity_match_score), interpretability schema (Evidence, ExplanationPayload, InterpretableSignal), timeline feedback (suggestion generation from signals).
- **Rules**: All signals must be traceable to raw events (evidence.contributing_event_ids). No signal is returned for display without evidence, explanation, and recommendation. Read-only use of event store; no document or questionnaire content.

### 4. Experience Layer

- **Responsibility**: API endpoints, RBAC enforcement, data visibility (researcher vs supervisor vs admin); serve only data allowed by role; return interpretable signals only (no raw signals without payload).
- **Components**: `api/v1/endpoints/*`, `core/security.py`, `core/data_visibility.py`. Routes: documents, analytics, supervisor, admin, events, engagement, intelligence, timeline-feedback.
- **Rules**: Admin endpoints expose only aggregated data; no document content or raw questionnaire answers. Intelligence endpoints return only `for_display()` payloads (evidence + explanation + recommendation).

---

## Cross-Cutting Concerns

| Concern | Implementation |
|--------|----------------|
| **Role-based access control** | Roles: researcher, supervisor, institution_admin. Permissions (e.g. TIMELINE_EDIT, STUDENT_RISK_VISIBILITY). `get_current_user`, `require_roles`, `require_permission`. Data visibility: researcher = own, supervisor = assigned students, admin = aggregated/anonymized. |
| **Standardized event taxonomy** | `core/event_taxonomy.py`: fixed EventType enum; all events use these types. `source_module` identifies emitting module. Versioned metadata (`metadata.v`) for schema evolution. |
| **Immutable longitudinal event store** | `models/longitudinal_event.py`, `services/event_store.py`. Append-only; no update/delete. Schema: event_id, user_id, role, event_type, entity_type, entity_id, metadata (JSONB), timestamp, source_module. |
| **Manual override in stage classification** | Stage inference on document upload; user can **accept** or **override** suggested stage. Override stores override_reason and system_suggested_stage; emits `stage_override` event; triggers timeline regeneration. No auto-change of user's stage without action. |
| **Explicit entity state machines** | `core/state_machines.py`: Opportunity, SupervisionSession, Milestone, WritingVersion. Valid transitions only; `state_transition_service` validates and logs every transition to event store. |
| **Engagement engine** | Inactivity detection (14/30/45 days); reminder creation; monthly digest from event store. Engagement signals (low_engagement, writing_inactivity, supervision_drift) feed intelligence layer. |
| **Interpretability layer** | Every intelligence signal carries Evidence (contributing_event_ids, time_window), Explanation, Recommendation. `InterpretableSignal.for_display()` is the only way to expose a signal; `require_explanation_payload()` enforces presence. |
| **Institutional analytics** | Admin-only; aggregation only. Cohort continuity, risk segmentation, supervisor engagement averages, stage distribution, timeline delay frequency. No document content; no raw questionnaire answers; aggregation threshold to prevent single-user inference. |
| **Timeline feedback loop** | Signals (milestone delay, supervision inactivity, writing stagnation) generate timeline_adjustment_suggestion. User accepts or rejects; suggestion_event, acceptance_event, rejection_event logged. Timeline remains user-controlled; no auto-modification of milestones. |

---

## Data Flow and Traceability

1. **Input → Event normalization**: User action (e.g. document upload, milestone completed) is handled in the Input layer. The handler creates/updates domain entities and calls `emit_event()` with a taxonomy event type and minimal metadata (entity_id, etc.). No document content or questionnaire answers are written into the event store.

2. **Event store as single source of truth**: All such events are stored in `longitudinal_events`. Each row has `event_id`, which is the stable reference for traceability.

3. **Intelligence reads events only**: Engagement engine and intelligence signals service query the event store (and optionally progress/timeline aggregates) to compute signals. For each signal they attach **evidence**: `contributing_event_ids` (list of `event_id`) and `time_window`. Thus every signal is traceable back to raw events.

4. **No signal without evidence and explanation**: The interpretability layer requires Evidence + Explanation + Recommendation for every InterpretableSignal. The Experience layer exposes only `for_display()` payloads; no “naked” signal value is returned. So no signal exists in the API without evidence and explanation.

5. **Experience layer**: Reads events (audit API) and intelligence outputs (interpretable signals); never reads document content or raw questionnaire answers for admin. Admin analytics use only aggregated counts and thresholds.

---

## Module Map by Layer

| Layer | Modules / Packages |
|-------|--------------------|
| **Input** | `services/document_service`, `services/questionnaire_draft_service`, `services/progress_service`, `services/stage_suggestion_service`, `services/state_transition_service`, `services/timeline_feedback_service`, `orchestrators/*` (when they emit events) |
| **Event normalization** | `core/event_taxonomy`, `core/state_machines`, `services/event_store`, `models/longitudinal_event`, `services/state_transition_service` (transition logging) |
| **Intelligence** | `core/interpretability`, `services/engagement_engine`, `services/intelligence_signals_service`, `services/timeline_feedback_service` (suggestion generation from signals), `services/stage_classification_engine` (inference only) |
| **Experience** | `api/v1/endpoints/*`, `core/security`, `core/data_visibility` |

Shared models (User, CommittedTimeline, etc.) are used across layers; the **event store and taxonomy** are the contract between Input/Event normalization and Intelligence/Experience.

---

## Principles

1. **Strict layer separation**: Experience → Intelligence → Event normalization → Input. Dependencies point downward only (or to the event store).
2. **All signals traceable to raw events**: Evidence must include `contributing_event_ids` (longitudinal event_id) and `time_window`. Consumers can resolve event_id to the row in `longitudinal_events`.
3. **No signal without evidence and explanation**: Any value exposed as an “intelligence signal” must be wrapped in InterpretableSignal with Evidence, Explanation, and Recommendation. Display uses only `for_display()`.
4. **No document content or raw questionnaire answers** in event store or in admin/analytics outputs.
5. **User-controlled timeline**: Timeline feedback suggests only; user accepts or rejects. No automatic modification of milestones.
6. **Immutable event store**: Append-only; no updates or deletes. Audit and traceability rely on this.
