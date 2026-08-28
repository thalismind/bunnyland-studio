"""Typed Studio domain events."""

from __future__ import annotations

from bunnyland.core.events import DomainEvent


class StudioInfluenceClaimedEvent(DomainEvent):
    character_id: str
    claim_id: str


class StudioInfluenceReleasedEvent(DomainEvent):
    character_id: str
    claim_id: str


class VanBreakdownOccurredEvent(DomainEvent):
    character_id: str
    incident_id: str
    location_id: str


class VanBreakdownExplainedEvent(DomainEvent):
    character_id: str
    incident_id: str
    diagnosis: str


__all__ = [
    "StudioInfluenceClaimedEvent",
    "StudioInfluenceReleasedEvent",
    "VanBreakdownExplainedEvent",
    "VanBreakdownOccurredEvent",
]
