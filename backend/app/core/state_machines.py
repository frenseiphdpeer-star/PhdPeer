"""
Explicit state machines for Opportunity, Supervision Session, Milestone, Writing Version.

Valid transitions only; transition logging and timestamps are handled by state_transition_service.
"""

from typing import Dict, Set

# ---------------------------------------------------------------------------
# Opportunity (user-opportunity): saved → applied → rejected|accepted → outcome_logged
# ---------------------------------------------------------------------------
OPPORTUNITY_STATES = {"saved", "applied", "rejected", "accepted", "outcome_logged"}
OPPORTUNITY_INITIAL_STATE = "saved"

OPPORTUNITY_TRANSITIONS: Dict[str, Set[str]] = {
    "saved": {"applied"},
    "applied": {"rejected", "accepted"},
    "rejected": {"outcome_logged"},
    "accepted": {"outcome_logged"},
    "outcome_logged": set(),
}


def opportunity_can_transition(from_state: str, to_state: str) -> bool:
    if from_state not in OPPORTUNITY_TRANSITIONS:
        return False
    return to_state in OPPORTUNITY_TRANSITIONS[from_state]


# ---------------------------------------------------------------------------
# Supervision Session: scheduled → occurred → feedback_pending → feedback_logged
# ---------------------------------------------------------------------------
SUPERVISION_SESSION_STATES = {"scheduled", "occurred", "feedback_pending", "feedback_logged"}
SUPERVISION_SESSION_INITIAL_STATE = "scheduled"

SUPERVISION_SESSION_TRANSITIONS: Dict[str, Set[str]] = {
    "scheduled": {"occurred"},
    "occurred": {"feedback_pending"},
    "feedback_pending": {"feedback_logged"},
    "feedback_logged": set(),
}


def supervision_session_can_transition(from_state: str, to_state: str) -> bool:
    if from_state not in SUPERVISION_SESSION_TRANSITIONS:
        return False
    return to_state in SUPERVISION_SESSION_TRANSITIONS[from_state]


# ---------------------------------------------------------------------------
# Milestone: upcoming → active → completed | delayed
# ---------------------------------------------------------------------------
MILESTONE_STATES = {"upcoming", "active", "completed", "delayed"}
MILESTONE_INITIAL_STATE = "upcoming"

MILESTONE_TRANSITIONS: Dict[str, Set[str]] = {
    "upcoming": {"active"},
    "active": {"completed", "delayed"},
    "delayed": {"active", "completed"},
    "completed": set(),
}


def milestone_can_transition(from_state: str, to_state: str) -> bool:
    if from_state not in MILESTONE_TRANSITIONS:
        return False
    return to_state in MILESTONE_TRANSITIONS[from_state]


# ---------------------------------------------------------------------------
# Writing Version: draft → revised → submitted → archived
# ---------------------------------------------------------------------------
WRITING_VERSION_STATES = {"draft", "revised", "submitted", "archived"}
WRITING_VERSION_INITIAL_STATE = "draft"

WRITING_VERSION_TRANSITIONS: Dict[str, Set[str]] = {
    "draft": {"revised", "submitted"},
    "revised": {"submitted", "archived"},
    "submitted": {"archived"},
    "archived": set(),
}


def writing_version_can_transition(from_state: str, to_state: str) -> bool:
    if from_state not in WRITING_VERSION_TRANSITIONS:
        return False
    return to_state in WRITING_VERSION_TRANSITIONS[from_state]


def get_allowed_next_states(entity_type: str, current_state: str) -> Set[str]:
    """Return set of valid next states for a given entity type and current state (for API/dashboard)."""
    maps = {
        "opportunity": OPPORTUNITY_TRANSITIONS,
        "supervision_session": SUPERVISION_SESSION_TRANSITIONS,
        "milestone": MILESTONE_TRANSITIONS,
        "writing_version": WRITING_VERSION_TRANSITIONS,
    }
    trans = maps.get(entity_type, {})
    return trans.get(current_state, set())

