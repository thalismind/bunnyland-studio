"""Persistent ECS contracts owned by Bunnyland Studio."""

from __future__ import annotations

from typing import Literal

from pydantic import Field
from pydantic.dataclasses import dataclass
from relics import Component, Edge


@dataclass(frozen=True)
class GeoPoint:
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


@dataclass(frozen=True)
class StudioInfluenceClaimComponent(Component):
    """Singleton ownership state on the one Studio-bound main character."""

    claim_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    owner_subject: str = Field(min_length=1, max_length=256)
    claimed_at_epoch: int = Field(ge=0)
    last_activity_epoch: int = Field(ge=0)


@dataclass(frozen=True)
class StudioInfluenceComponent(Component):
    influence_id: str
    category: Literal["want", "need", "suggestion"]
    text: str = Field(min_length=1, max_length=1000)
    created_at_epoch: int = Field(ge=0)
    strength: Literal["soft", "core"] = "soft"
    pressure: Literal["low", "balanced", "strong"] = "balanced"
    need: Literal[
        "",
        "hunger",
        "thirst",
        "fatigue",
        "hygiene",
        "comfort",
        "fun",
        "social",
        "privacy",
        "safety",
    ] = ""
    need_delta: float = Field(default=0, ge=-25, le=25)
    goal_text: str = ""


@dataclass(frozen=True)
class StudioRouteComponent(Component):
    route_id: str
    title: str = Field(min_length=1, max_length=160)
    created_at_epoch: int = Field(ge=0)
    adherence: Literal["loose", "balanced", "strict"] = "balanced"
    status: Literal["planned", "active", "paused", "completed"] = "planned"
    current_waypoint: int = Field(default=0, ge=0)


@dataclass(frozen=True)
class StudioLocationComponent(Component):
    location_id: str
    name: str
    kind: Literal["town", "neighborhood", "camp", "fuel", "food", "attraction", "repair", "road"]
    point: GeoPoint
    osm_type: str = ""
    osm_id: int | None = None
    visible_globally: bool = True


@dataclass(frozen=True)
class StudioRoadComponent(Component):
    road_id: str
    from_location_id: str
    to_location_id: str
    distance_km: float = Field(gt=0)
    travel_minutes: int = Field(gt=0)
    hierarchy: Literal["highway", "secondary", "local"] = "secondary"


@dataclass(frozen=True)
class StudioVanComponent(Component):
    name: str
    description: str
    current_location_id: str
    fuel_liters: float = Field(ge=0)
    tank_liters: float = Field(gt=0)
    km_per_liter: float = Field(gt=0)
    reliability: Literal["temperamental", "fair", "dependable"] = "fair"
    broken_down: bool = False
    completed_legs: int = Field(default=0, ge=0)
    breakdown_cooldown_legs: int = Field(default=0, ge=0)
    active_incident_id: str = ""


@dataclass(frozen=True)
class StudioTravelSegmentComponent(Component):
    segment_id: str
    from_location_id: str
    to_location_id: str
    distance_km: float = Field(ge=0)
    occurred_at_epoch: int = Field(ge=0)
    kind: Literal["route", "detour", "skipped"] = "route"


@dataclass(frozen=True)
class StudioBreakdownComponent(Component):
    incident_id: str
    location_id: str
    event_seed: int
    occurred_at_epoch: int = Field(ge=0)
    diagnosis: str = ""
    symptoms: tuple[str, ...] = ()
    explanation: str = ""
    recommendation: str = ""
    narrative_source: Literal["pending", "world-agent", "fallback"] = "pending"


@dataclass(frozen=True)
class StudioJournalMomentComponent(Component):
    moment_id: str
    kind: Literal["arrival", "breakdown", "encounter", "reflection", "media", "note"]
    summary: str
    occurred_at_epoch: int = Field(ge=0)
    location_id: str = ""
    first_person: bool = False
    pinned: bool = False
    media_job_id: str = ""
    media_kind: Literal["", "image", "video"] = ""


@dataclass(frozen=True)
class StudioGeographyComponent(Component):
    mode: Literal["real", "fictional"]
    title: str
    attribution: str
    tile_url: str = ""
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class StudioOwns(Edge):
    kind: Literal["influence", "route", "segment", "incident", "journal", "van", "geography"]


@dataclass(frozen=True)
class StudioRouteWaypoint(Edge):
    order: int = Field(ge=0)


__all__ = [name for name in globals() if name.startswith("Studio") or name == "GeoPoint"]
