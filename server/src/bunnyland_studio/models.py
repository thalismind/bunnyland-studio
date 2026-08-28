"""Typed Studio HTTP and world-generator contracts."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, JsonValue

from .components import GeoPoint


class StudioModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_default=True)


class ClaimRequest(StudioModel):
    character_id: str


class ClaimResource(StudioModel):
    claim_id: str
    character_id: str
    owner_subject: str
    claimed_at_epoch: int
    last_activity_epoch: int
    autonomous_controller_active: bool


class CharacterChoice(StudioModel):
    id: str
    name: str
    claimed: bool


class InfluenceResource(StudioModel):
    id: str
    category: str
    strength: str
    pressure: str
    text: str
    need: str = ""
    need_delta: float = 0


class VanResource(StudioModel):
    name: str
    description: str
    fuel_liters: float
    tank_liters: float
    estimated_range_km: float
    reliability: str
    broken_down: bool
    current_location_id: str
    autonomous_controller_active: bool


class SceneResource(StudioModel):
    room_id: str = ""
    room_name: str = ""
    visible_characters: list[str] = Field(default_factory=list)


class ProjectionResource(StudioModel):
    world_epoch: int
    character_id: str
    character_name: str
    claim: ClaimResource
    van: VanResource | None = None
    scene: SceneResource
    influences: list[InfluenceResource] = Field(default_factory=list)
    media_available: dict[Literal["image", "video"], bool]


class RouteResource(StudioModel):
    id: str
    title: str
    adherence: str
    status: str
    current_waypoint: int
    waypoints: list[str]


class JournalResource(StudioModel):
    id: str
    kind: str
    summary: str
    location_id: str
    occurred_at_epoch: int
    first_person: bool
    pinned: bool
    media_job_id: str
    media_kind: str
    media_source_event_id: str
    media_status: Literal["", "queued", "running", "succeeded", "failed", "expired"]
    media_url: str
    media_error: str


class ReflectionRequest(StudioModel):
    text: str = Field(min_length=1, max_length=4000)


class MediaJobResource(StudioModel):
    id: str
    kind: str
    status: str
    source_event_id: str
    url: str
    error: str | None = None


class InfluenceRequest(StudioModel):
    category: Literal["want", "need", "suggestion"]
    strength: Literal["soft", "core"] = "soft"
    pressure: Literal["low", "balanced", "strong"] = "balanced"
    text: str = Field(min_length=1, max_length=1000)
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


class MemoryRequest(StudioModel):
    text: str = Field(min_length=1, max_length=4000)
    tags: tuple[str, ...] = ()


class MemoryResource(StudioModel):
    id: str
    source: str
    created_at_epoch: int


class RouteWaypointRequest(StudioModel):
    location_id: str


class RouteRequest(StudioModel):
    title: str = Field(min_length=1, max_length=160)
    adherence: Literal["loose", "balanced", "strict"] = "balanced"
    waypoints: tuple[RouteWaypointRequest, ...] = Field(min_length=1, max_length=64)


class MediaRequest(StudioModel):
    kind: Literal["image", "video"]
    event_id: str = ""


class StudioBlueprint(StudioModel):
    character_name: str
    pronouns: str = "she/her"
    appearance: str
    persona: str
    travel_motivation: str
    van_name: str
    van_description: str
    tank_liters: float = Field(default=60, gt=0, le=200)
    starting_fuel_liters: float = Field(default=60, ge=0, le=200)
    km_per_liter: float = Field(default=9, gt=0, le=30)
    reliability: Literal["temperamental", "fair", "dependable"] = "fair"
    anime_direction: str = "cinematic anime road movie, grounded factual scene"


class LocationSelection(StudioModel):
    id: str
    name: str
    point: GeoPoint
    osm_type: str = ""
    osm_id: int | None = None


class OverpassCenter(StudioModel):
    lat: float
    lon: float


class OverpassPoi(StudioModel):
    type: Literal["node", "way", "relation"]
    id: int
    lat: float | None = None
    lon: float | None = None
    center: OverpassCenter | None = None
    tags: dict[str, str] = Field(default_factory=dict)


class RealGeneratorConfig(StudioModel):
    blueprint: StudioBlueprint
    origin: LocationSelection
    destinations: tuple[LocationSelection, ...] = Field(min_length=1, max_length=20)
    nominatim_url: HttpUrl = "https://nominatim.openstreetmap.org"
    osrm_url: HttpUrl = "https://router.project-osrm.org"
    overpass_url: HttpUrl = "https://overpass-api.de/api/interpreter"
    tile_url: str = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
    contact: str = Field(min_length=3)


class FictionalGeneratorConfig(StudioModel):
    blueprint: StudioBlueprint
    region_name: str = "Roseglass Highways"
    town_count: int = Field(default=8, ge=4, le=24)
    branch_count: int = Field(default=3, ge=1, le=8)


class BreakdownNarrative(StudioModel):
    diagnosis: str = Field(min_length=3, max_length=160)
    symptoms: tuple[str, ...] = Field(min_length=1, max_length=5)
    explanation: str = Field(min_length=3, max_length=800)
    recommendation: str = Field(min_length=3, max_length=300)


class MapLocation(StudioModel):
    id: str
    name: str
    kind: str
    point: GeoPoint


class MapSegment(StudioModel):
    id: str
    from_location_id: str
    to_location_id: str
    state: Literal["future", "completed", "detour", "skipped"]
    distance_km: float
    occurred_at_epoch: int | None = None


class MapResource(StudioModel):
    mode: Literal["real", "fictional"]
    attribution: str
    tile_url: str = ""
    current_location_id: str
    locations: list[MapLocation]
    segments: list[MapSegment]
    warnings: list[str] = Field(default_factory=list)


class GeneratorConfigResource(StudioModel):
    real: dict[str, JsonValue]
    fictional_generator: Literal["studio-van-waifu-fictional"]
    real_generator: Literal["studio-van-waifu-real"]


__all__ = [name for name in globals() if name[0].isupper() and name != "BaseModel"]
