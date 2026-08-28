"""Real-map and deterministic fictional Van Waifu whole-world generators."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from hashlib import sha256
from urllib.parse import quote

import httpx
from bunnyland.core.ecs import spawn_entity
from bunnyland.worldgen import (
    CharacterSpec,
    ExitSpec,
    GenOptions,
    ObjectSpec,
    RoomSpec,
    WorldGenerator,
    WorldProposal,
    instantiate,
)

from .components import (
    GeoPoint,
    StudioGeographyComponent,
    StudioLocationComponent,
    StudioOwns,
    StudioRoadComponent,
    StudioRouteComponent,
    StudioRouteWaypoint,
    StudioVanComponent,
)
from .models import FictionalGeneratorConfig, LocationSelection, OverpassPoi, RealGeneratorConfig

OSM_ATTRIBUTION = "© OpenStreetMap contributors (ODbL)"
REAL_GENERATOR_NAME = "studio-van-waifu-real"
FICTIONAL_GENERATOR_NAME = "studio-van-waifu-fictional"


@dataclass(frozen=True)
class RouteEstimate:
    distance_km: float
    travel_minutes: int


@dataclass(frozen=True)
class LocationPlan:
    selection: LocationSelection
    kind: str = "town"


@dataclass(frozen=True)
class RoadPlan:
    from_index: int
    to_index: int
    estimate: RouteEstimate
    hierarchy: str = "secondary"


class OpenMapClient:
    """Bounded generation-time Nominatim, OSRM, and Overpass client."""

    def __init__(
        self,
        *,
        nominatim_url: str,
        osrm_url: str,
        overpass_url: str,
        contact: str,
        timeout_seconds: float = 12,
    ) -> None:
        self.nominatim_url = nominatim_url.rstrip("/")
        self.osrm_url = osrm_url.rstrip("/")
        self.overpass_url = overpass_url.rstrip("/")
        self.headers = {"User-Agent": f"bunnyland-studio/0.1 ({contact})"}
        self.timeout = timeout_seconds
        self._search_cache: dict[str, tuple[LocationSelection, ...]] = {}
        self._route_cache: dict[tuple[GeoPoint, GeoPoint], RouteEstimate] = {}

    async def search(self, query: str, *, limit: int = 5) -> tuple[LocationSelection, ...]:
        key = f"{query.strip().lower()}:{min(max(limit, 1), 10)}"
        if key in self._search_cache:
            return self._search_cache[key]
        async with httpx.AsyncClient(timeout=self.timeout, headers=self.headers) as client:
            response = await client.get(
                f"{self.nominatim_url}/search",
                params={"q": query, "format": "jsonv2", "limit": min(max(limit, 1), 10)},
            )
            response.raise_for_status()
        results: list[LocationSelection] = []
        for item in response.json()[:10]:
            if not isinstance(item, dict):
                continue
            results.append(
                LocationSelection(
                    id=f"osm:{item.get('osm_type', '')}:{item.get('osm_id', '')}",
                    name=str(item.get("display_name", "Unknown place")),
                    point=GeoPoint(latitude=float(item["lat"]), longitude=float(item["lon"])),
                    osm_type=str(item.get("osm_type", "")),
                    osm_id=int(item["osm_id"]) if item.get("osm_id") is not None else None,
                )
            )
        value = tuple(results)
        self._search_cache[key] = value
        return value

    async def route(self, start: GeoPoint, end: GeoPoint) -> RouteEstimate:
        key = (start, end)
        if key in self._route_cache:
            return self._route_cache[key]
        coordinates = f"{start.longitude},{start.latitude};{end.longitude},{end.latitude}"
        async with httpx.AsyncClient(timeout=self.timeout, headers=self.headers) as client:
            response = await client.get(
                f"{self.osrm_url}/route/v1/driving/{quote(coordinates, safe=',;.')}",
                params={"overview": "false", "alternatives": "false", "steps": "false"},
            )
            response.raise_for_status()
        routes = response.json().get("routes", [])
        if not routes:
            raise RuntimeError("OSRM returned no driving route")
        estimate = RouteEstimate(
            distance_km=float(routes[0]["distance"]) / 1000,
            travel_minutes=max(1, round(float(routes[0]["duration"]) / 60)),
        )
        self._route_cache[key] = estimate
        return estimate

    async def pois(
        self, center: GeoPoint, *, radius_meters: int = 25_000
    ) -> tuple[OverpassPoi, ...]:
        bounded_radius = min(max(radius_meters, 1000), 50_000)
        query = (
            "[out:json][timeout:20];("
            f"nwr[amenity=fuel](around:{bounded_radius},{center.latitude},{center.longitude});"
            f'nwr[amenity~"^(restaurant|cafe|fast_food)$"]'
            f"(around:{bounded_radius},{center.latitude},{center.longitude});"
            f"nwr[tourism=camp_site](around:{bounded_radius},{center.latitude},{center.longitude});"
            f'nwr[tourism~"^(attraction|museum|viewpoint)$"]'
            f"(around:{bounded_radius},{center.latitude},{center.longitude});"
            f"nwr[shop=car_repair](around:{bounded_radius},{center.latitude},{center.longitude});"
            ");out center 50;"
        )
        async with httpx.AsyncClient(timeout=self.timeout, headers=self.headers) as client:
            response = await client.post(self.overpass_url, content=query)
            response.raise_for_status()
        elements = response.json().get("elements", [])
        results: list[OverpassPoi] = []
        for item in elements[:50]:
            if not isinstance(item, dict):
                continue
            try:
                results.append(OverpassPoi.model_validate(item))
            except ValueError:
                continue
        return tuple(results)


def _poi_kind(poi: OverpassPoi) -> str | None:
    if poi.tags.get("amenity") == "fuel":
        return "fuel"
    if poi.tags.get("tourism") == "camp_site":
        return "camp"
    if poi.tags.get("shop") in {"car_repair", "tyres"}:
        return "repair"
    if poi.tags.get("amenity") in {"restaurant", "cafe", "fast_food"}:
        return "food"
    if poi.tags.get("tourism") in {"attraction", "museum", "viewpoint"}:
        return "attraction"
    return None


def _poi_selection(poi: OverpassPoi) -> LocationSelection | None:
    point = (
        GeoPoint(latitude=poi.lat, longitude=poi.lon)
        if poi.lat is not None and poi.lon is not None
        else GeoPoint(latitude=poi.center.lat, longitude=poi.center.lon)
        if poi.center is not None
        else None
    )
    if point is None:
        return None
    return LocationSelection(
        id=f"osm:{poi.type}:{poi.id}",
        name=poi.tags.get("name", f"OSM {poi.type} {poi.id}"),
        point=point,
        osm_type=poi.type,
        osm_id=poi.id,
    )


def _stable_seed(seed: str) -> int:
    return int.from_bytes(sha256(seed.encode()).digest()[:8], "big")


def _slug(value: str, index: int) -> str:
    letters = "".join(character.lower() if character.isalnum() else "-" for character in value)
    normalized = "-".join(part for part in letters.split("-") if part)
    return f"{normalized or 'location'}-{index}"


async def _instantiate_studio(
    actor,
    *,
    seed: str,
    mode: str,
    title: str,
    attribution: str,
    tile_url: str,
    blueprint,
    locations: tuple[LocationPlan, ...],
    roads: tuple[RoadPlan, ...],
    itinerary_count: int,
    warnings: tuple[str, ...] = (),
):
    selections = tuple(location.selection for location in locations)
    room_keys = tuple(_slug(location.name, index) for index, location in enumerate(selections))
    proposal = WorldProposal(
        seed=seed,
        rooms=[
            RoomSpec(
                key=key,
                title=location.name,
                biome="road-trip-town" if index else "road-trip-origin",
                indoor=False,
                description=f"A Studio travel location: {location.name}.",
            )
            for index, (key, location) in enumerate(zip(room_keys, selections, strict=True))
        ],
        exits=[
            edge
            for index, road in enumerate(roads)
            for edge in (
                ExitSpec(
                    from_key=room_keys[road.from_index],
                    direction=f"road-{index}",
                    to_key=room_keys[road.to_index],
                ),
                ExitSpec(
                    from_key=room_keys[road.to_index],
                    direction=f"back-{index}",
                    to_key=room_keys[road.from_index],
                ),
            )
        ],
        characters=[
            CharacterSpec(
                key="main-character",
                name=blueprint.character_name,
                room_key=room_keys[0],
                controller="llm",
                llm_profile="studio-van-waifu",
                traits=(blueprint.persona, blueprint.pronouns, blueprint.appearance),
                goals=(blueprint.travel_motivation,),
                with_needs=True,
                with_memory=True,
            )
        ],
        objects=[
            ObjectSpec(
                key="studio-van",
                room_key=room_keys[0],
                name=blueprint.van_name,
                kind="mobile-home-van",
                portable=False,
                description=blueprint.van_description,
            )
        ],
    )
    result = await instantiate(actor, proposal)
    character = actor.world.get_entity(result.characters["main-character"])
    van = actor.world.get_entity(result.objects["studio-van"])
    van.add_component(
        StudioVanComponent(
            name=blueprint.van_name,
            description=blueprint.van_description,
            fuel_liters=min(blueprint.starting_fuel_liters, blueprint.tank_liters),
            tank_liters=blueprint.tank_liters,
            km_per_liter=blueprint.km_per_liter,
            reliability=blueprint.reliability,
            current_location_id=selections[0].id,
        )
    )
    character.add_relationship(StudioOwns(kind="van"), van.id)
    geography = spawn_entity(
        actor.world,
        [
            StudioGeographyComponent(
                mode=mode,
                title=title,
                attribution=attribution,
                tile_url=tile_url,
                warnings=warnings,
            )
        ],
    )
    character.add_relationship(StudioOwns(kind="geography"), geography.id)
    location_entities = []
    for index, location_plan in enumerate(locations):
        location = location_plan.selection
        room = actor.world.get_entity(result.rooms[room_keys[index]])
        room.add_component(
            StudioLocationComponent(
                location_id=location.id,
                name=location.name,
                kind=location_plan.kind,
                point=location.point,
                osm_type=location.osm_type,
                osm_id=location.osm_id,
            )
        )
        location_entities.append(room)
    for index, road in enumerate(roads):
        spawn_entity(
            actor.world,
            [
                StudioRoadComponent(
                    road_id=f"road-{index}",
                    from_location_id=selections[road.from_index].id,
                    to_location_id=selections[road.to_index].id,
                    distance_km=road.estimate.distance_km,
                    travel_minutes=road.estimate.travel_minutes,
                    hierarchy=road.hierarchy,
                )
            ],
        )
    route = spawn_entity(
        actor.world,
        [
            StudioRouteComponent(
                route_id=uuid_from(seed),
                title=f"{title} itinerary",
                status="active",
                created_at_epoch=actor.epoch,
            )
        ],
    )
    for order, location in enumerate(location_entities[:itinerary_count]):
        route.add_relationship(StudioRouteWaypoint(order=order), location.id)
    character.add_relationship(StudioOwns(kind="route"), route.id)
    return result


def uuid_from(seed: str) -> str:
    return sha256(f"studio-route:{seed}".encode()).hexdigest()[:32]


async def real_generator(actor, seed: str, options: GenOptions):
    config = RealGeneratorConfig.model_validate(options.generator_config)
    selections = (config.origin, *config.destinations)
    client = OpenMapClient(
        nominatim_url=str(config.nominatim_url),
        osrm_url=str(config.osrm_url),
        overpass_url=str(config.overpass_url),
        contact=config.contact,
    )
    estimate_list: list[RouteEstimate] = []
    for start, end in zip(selections, selections[1:], strict=False):
        estimate_list.append(await client.route(start.point, end.point))
    estimates = tuple(estimate_list)
    road_plans = [
        RoadPlan(index, index + 1, estimate, "highway") for index, estimate in enumerate(estimates)
    ]
    locations = [LocationPlan(selection) for selection in selections]
    seen = {selection.id for selection in selections}
    for parent_index, selection in enumerate(selections[:5]):
        try:
            pois = await client.pois(selection.point)
        except (httpx.HTTPError, RuntimeError, ValueError):
            continue
        for poi in pois:
            kind = _poi_kind(poi)
            service = _poi_selection(poi)
            if kind is None or service is None or service.id in seen:
                continue
            try:
                estimate = await client.route(selection.point, service.point)
            except (httpx.HTTPError, RuntimeError, ValueError):
                continue
            seen.add(service.id)
            service_index = len(locations)
            locations.append(LocationPlan(service, kind))
            road_plans.append(RoadPlan(parent_index, service_index, estimate, "local"))
            if len(locations) - len(selections) >= 20:
                break
        if len(locations) - len(selections) >= 20:
            break
    estimated_range = config.blueprint.starting_fuel_liters * config.blueprint.km_per_liter
    warnings = tuple(
        f"No mapped fuel stop is guaranteed across the {estimate.distance_km:.1f} km leg "
        f"from {start.name} to {end.name}; estimated van range is {estimated_range:.1f} km."
        for start, end, estimate in zip(selections[:-1], selections[1:], estimates, strict=True)
        if estimate.distance_km > estimated_range
    )
    return await _instantiate_studio(
        actor,
        seed=seed,
        mode="real",
        title="Van Waifu real-map journey",
        attribution=OSM_ATTRIBUTION,
        tile_url=config.tile_url,
        blueprint=config.blueprint,
        locations=tuple(locations),
        roads=tuple(road_plans),
        itinerary_count=len(selections),
        warnings=warnings,
    )


def fictional_plan(
    seed: str, config: FictionalGeneratorConfig
) -> tuple[tuple[LocationPlan, ...], tuple[RoadPlan, ...]]:
    rng = random.Random(_stable_seed(seed))
    names_a = ("Rose", "Copper", "Moon", "Juniper", "Glass", "Cinder", "Blue", "Moss")
    names_b = ("Junction", "Hollow", "Crossing", "Bay", "Mesa", "Springs", "Reach", "Vale")
    locations: list[LocationPlan] = []
    for index in range(config.town_count):
        angle = (2 * math.pi * index / config.town_count) + rng.uniform(-0.15, 0.15)
        radius = 0.5 + index * 0.18
        name = f"{names_a[index % len(names_a)]} {names_b[(index * 3) % len(names_b)]}"
        locations.append(
            LocationPlan(
                LocationSelection(
                    id=f"fictional:town:{index}",
                    name=name,
                    point=GeoPoint(
                        latitude=round(35 + math.sin(angle) * radius, 6),
                        longitude=round(-105 + math.cos(angle) * radius, 6),
                    ),
                )
            )
        )
    roads: list[RoadPlan] = [
        RoadPlan(
            index,
            index + 1,
            RouteEstimate(
                distance_km=round(35 + rng.random() * 35, 1),
                travel_minutes=45 + rng.randrange(50),
            ),
            "highway" if index < 2 else "secondary",
        )
        for index in range(config.town_count - 1)
    ]
    roads.append(
        RoadPlan(
            config.town_count - 1,
            0,
            RouteEstimate(distance_km=round(55 + rng.random() * 40, 1), travel_minutes=105),
            "highway",
        )
    )
    service_kinds = ("fuel", "camp", "repair", "attraction", "neighborhood")
    for branch in range(config.branch_count):
        parent_index = 1 + (branch * 2) % (config.town_count - 1)
        parent = locations[parent_index].selection
        kind = service_kinds[branch % len(service_kinds)]
        service_index = len(locations)
        locations.append(
            LocationPlan(
                LocationSelection(
                    id=f"fictional:{kind}:{branch}",
                    name=f"{parent.name} {kind.title()}",
                    point=GeoPoint(
                        latitude=round(parent.point.latitude + rng.uniform(-0.12, 0.12), 6),
                        longitude=round(parent.point.longitude + rng.uniform(-0.12, 0.12), 6),
                    ),
                ),
                kind,
            )
        )
        roads.append(
            RoadPlan(
                parent_index,
                service_index,
                RouteEstimate(
                    distance_km=round(8 + rng.random() * 18, 1),
                    travel_minutes=15 + rng.randrange(25),
                ),
                "local",
            )
        )
    return tuple(locations), tuple(roads)


async def fictional_generator(actor, seed: str, options: GenOptions):
    config = FictionalGeneratorConfig.model_validate(options.generator_config)
    locations, roads = fictional_plan(seed, config)
    return await _instantiate_studio(
        actor,
        seed=seed,
        mode="fictional",
        title=config.region_name,
        attribution="Fictional geography generated by Bunnyland Studio",
        tile_url="",
        blueprint=config.blueprint,
        locations=locations,
        roads=roads,
        itinerary_count=config.town_count,
    )


REAL_GENERATOR = WorldGenerator(
    name=REAL_GENERATOR_NAME,
    generate=real_generator,
    description="Van Waifu journey using Nominatim, OSRM, and bounded Overpass data.",
    group="studio",
)
FICTIONAL_GENERATOR = WorldGenerator(
    name=FICTIONAL_GENERATOR_NAME,
    generate=fictional_generator,
    description="Deterministic connected fictional Van Waifu road network.",
    group="studio",
)

__all__ = [
    "FICTIONAL_GENERATOR",
    "FICTIONAL_GENERATOR_NAME",
    "OSM_ATTRIBUTION",
    "OpenMapClient",
    "REAL_GENERATOR",
    "REAL_GENERATOR_NAME",
    "RouteEstimate",
    "LocationPlan",
    "RoadPlan",
    "fictional_plan",
]
