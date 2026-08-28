"""Owner-scoped Studio projections and administrator setup routes."""

from __future__ import annotations

import asyncio
import time
from dataclasses import replace

from bunnyland.core import CharacterComponent, ControlledBy, IdentityComponent
from bunnyland.core.ecs import replace_component
from bunnyland.foundation.history.mechanics import history_record_for_event
from bunnyland.imagegen.components import EventImageComponent, EventVideoComponent
from bunnyland.plugins import AddonMediaCapability, PlayWebSocketAuthCapability
from bunnyland.server import serialize_character_projection
from bunnyland.server.app import (
    PLAYER_WEBSOCKET_AUTH_SECONDS,
    WEBSOCKET_REAUTHORIZE_SECONDS,
    next_player_update,
    websocket_origin_is_trusted,
)
from bunnyland.server.auth import TokenPrincipal
from fastapi import HTTPException, Request, WebSocket, WebSocketDisconnect

from .components import (
    StudioGeographyComponent,
    StudioInfluenceClaimComponent,
    StudioInfluenceComponent,
    StudioJournalMomentComponent,
    StudioLocationComponent,
    StudioOwns,
    StudioRoadComponent,
    StudioRouteComponent,
    StudioRouteWaypoint,
    StudioTravelSegmentComponent,
    StudioVanComponent,
)
from .generators import OpenMapClient
from .mechanics import (
    add_influence,
    add_memory,
    character_entity,
    claim_character,
    claimed_character,
    controller_snapshot,
    create_route,
    record_journal,
    release_claim,
    remove_influence,
    reset_claim,
    touch_claim,
)
from .models import (
    CharacterChoice,
    ClaimRequest,
    ClaimResource,
    GeneratorConfigResource,
    InfluenceRequest,
    InfluenceResource,
    JournalResource,
    LocationSelection,
    MapLocation,
    MapResource,
    MapSegment,
    MediaJobResource,
    MediaRequest,
    MemoryRequest,
    MemoryResource,
    ProjectionResource,
    RealGeneratorConfig,
    ReflectionRequest,
    RouteRequest,
    RouteResource,
    SceneResource,
    VanResource,
)

MEDIA_REQUEST_WINDOW_SECONDS = 60
MEDIA_REQUEST_LIMIT = 4
_MEDIA_REQUESTS: dict[str, list[float]] = {}


def _subject(request: Request) -> str:
    principal = getattr(request.state, "auth_principal", None)
    if not isinstance(principal, TokenPrincipal):
        raise HTTPException(status_code=401, detail="authenticated account is required")
    return principal.subject


def _owner_character(actor, request: Request):
    try:
        return claimed_character(actor, _subject(request))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


def _claim_error(exc: Exception) -> HTTPException:
    if isinstance(exc, LookupError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, TypeError):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, PermissionError):
        return HTTPException(status_code=403, detail=str(exc))
    return HTTPException(status_code=409, detail=str(exc))


def _claim_resource(actor, character, claim) -> ClaimResource:
    controllers = character.get_relationships(ControlledBy)
    autonomous = bool(controllers) and actor._controller_kind(controllers[0][1]) not in {
        "web",
        "mcp",
        "discord",
    }
    return ClaimResource(
        claim_id=claim.claim_id,
        character_id=str(character.id),
        owner_subject=claim.owner_subject,
        claimed_at_epoch=claim.claimed_at_epoch,
        last_activity_epoch=claim.last_activity_epoch,
        autonomous_controller_active=autonomous,
    )


def _owned(actor, character, kind: str):
    for edge, target in character.get_relationships(StudioOwns):
        if edge.kind == kind and actor.world.has_entity(target):
            yield actor.world.get_entity(target)


def _influences(actor, character) -> list[InfluenceResource]:
    resources = []
    for entity in _owned(actor, character, "influence"):
        item = entity.get_component(StudioInfluenceComponent)
        resources.append(
            InfluenceResource(
                id=item.influence_id,
                category=item.category,
                strength=item.strength,
                pressure=item.pressure,
                text=item.text,
                need=item.need,
                need_delta=item.need_delta,
            )
        )
    return sorted(resources, key=lambda item: item.id)


def _route_resources(actor, character) -> list[RouteResource]:
    resources = []
    for entity in _owned(actor, character, "route"):
        route = entity.get_component(StudioRouteComponent)
        waypoints = [
            (edge.order, target)
            for edge, target in entity.get_relationships(StudioRouteWaypoint)
            if actor.world.has_entity(target)
        ]
        resources.append(
            RouteResource(
                id=route.route_id,
                title=route.title,
                adherence=route.adherence,
                status=route.status,
                current_waypoint=route.current_waypoint,
                waypoints=[
                    actor.world.get_entity(target)
                    .get_component(StudioLocationComponent)
                    .location_id
                    for _order, target in sorted(waypoints)
                ],
            )
        )
    return sorted(resources, key=lambda item: item.id)


def _journal_resources(actor, character) -> list[JournalResource]:
    resources = []
    for entity in _owned(actor, character, "journal"):
        item = entity.get_component(StudioJournalMomentComponent)
        resources.append(
            JournalResource(
                id=item.moment_id,
                kind=item.kind,
                summary=item.summary,
                location_id=item.location_id,
                occurred_at_epoch=item.occurred_at_epoch,
                first_person=item.first_person,
                pinned=item.pinned,
                media_job_id=item.media_job_id,
                media_kind=item.media_kind,
                media_source_event_id=item.media_source_event_id,
                media_status=item.media_status,
                media_url=item.media_url,
                media_error=item.media_error,
            )
        )
    return sorted(resources, key=lambda item: (item.occurred_at_epoch, item.id), reverse=True)[:500]


def _durable_media_url(actor, item: StudioJournalMomentComponent) -> str:
    if not item.media_source_event_id or not item.media_kind:
        return ""
    record = history_record_for_event(actor.world, item.media_source_event_id)
    if record is None:
        return ""
    if item.media_kind == "image" and record.has_component(EventImageComponent):
        return record.get_component(EventImageComponent).url
    if item.media_kind == "video" and record.has_component(EventVideoComponent):
        return record.get_component(EventVideoComponent).url
    return ""


def _normalized_media_status(status: str) -> str:
    if status in {"queued", "running", "succeeded", "failed"}:
        return status
    return "failed"


def _sync_journal_media(actor, character, media: AddonMediaCapability) -> None:
    """Persist live jobs and durable event media into owner-scoped journal moments."""

    for entity in _owned(actor, character, "journal"):
        item = entity.get_component(StudioJournalMomentComponent)
        if not item.media_job_id or not item.media_kind:
            continue
        job = media.get_character_scene_media_job(item.media_job_id, kind=item.media_kind)
        durable_url = _durable_media_url(actor, item)
        if durable_url:
            updated = replace(
                item,
                media_status="succeeded",
                media_url=durable_url,
                media_error="",
            )
        elif job is not None:
            status = _normalized_media_status(job.status)
            updated = replace(
                item,
                media_source_event_id=job.source_event_id,
                media_status=status,
                media_url=job.url,
                media_error=(
                    job.error or ""
                    if status != "failed" or job.error
                    else f"Media service returned an unsupported status: {job.status}"
                ),
            )
        elif item.media_status in {"", "queued", "running"}:
            updated = replace(
                item,
                media_status="expired",
                media_error="Media job state expired before completion; request it again.",
            )
        else:
            continue
        if updated != item:
            replace_component(entity, updated)


def _map_resource(actor, character) -> MapResource:
    geographies = list(_owned(actor, character, "geography"))
    geography = (
        geographies[0].get_component(StudioGeographyComponent)
        if geographies
        else StudioGeographyComponent(
            mode="fictional",
            title="Studio journey",
            attribution="Fictional geography generated by Bunnyland Studio",
        )
    )
    locations = [
        entity.get_component(StudioLocationComponent)
        for entity in actor.world.query().with_all([StudioLocationComponent]).execute_entities()
    ]
    location_resources = [
        MapLocation(id=item.location_id, name=item.name, kind=item.kind, point=item.point)
        for item in sorted(locations, key=lambda location: location.location_id)
    ]
    completed = []
    completed_pairs = set()
    for entity in _owned(actor, character, "segment"):
        item = entity.get_component(StudioTravelSegmentComponent)
        completed_pairs.add((item.from_location_id, item.to_location_id))
        completed.append(
            MapSegment(
                id=item.segment_id,
                from_location_id=item.from_location_id,
                to_location_id=item.to_location_id,
                state="detour" if item.kind == "detour" else item.kind,
                distance_km=item.distance_km,
                occurred_at_epoch=item.occurred_at_epoch,
            )
        )
    future = []
    for road_entity in actor.world.query().with_all([StudioRoadComponent]).execute_entities():
        road = road_entity.get_component(StudioRoadComponent)
        if (road.from_location_id, road.to_location_id) in completed_pairs:
            continue
        future.append(
            MapSegment(
                id=road.road_id,
                from_location_id=road.from_location_id,
                to_location_id=road.to_location_id,
                state="future",
                distance_km=road.distance_km,
            )
        )
    vans = list(_owned(actor, character, "van"))
    current = vans[0].get_component(StudioVanComponent).current_location_id if vans else ""
    return MapResource(
        mode=geography.mode,
        attribution=geography.attribution,
        tile_url=geography.tile_url,
        current_location_id=current,
        locations=location_resources,
        segments=sorted((*completed, *future), key=lambda segment: segment.id),
        warnings=list(geography.warnings),
    )


def _projection(actor, character, media: AddonMediaCapability) -> ProjectionResource:
    safe = serialize_character_projection(actor, str(character.id))
    claim = character.get_component(StudioInfluenceClaimComponent)
    vans = list(_owned(actor, character, "van"))
    van_resource = None
    autonomous = _claim_resource(actor, character, claim).autonomous_controller_active
    if vans:
        van = vans[0].get_component(StudioVanComponent)
        van_resource = VanResource(
            name=van.name,
            description=van.description,
            fuel_liters=van.fuel_liters,
            tank_liters=van.tank_liters,
            estimated_range_km=van.fuel_liters * van.km_per_liter,
            reliability=van.reliability,
            broken_down=van.broken_down,
            current_location_id=van.current_location_id,
            autonomous_controller_active=autonomous,
        )
    return ProjectionResource(
        world_epoch=actor.epoch,
        character_id=str(character.id),
        character_name=safe.character_name,
        claim=_claim_resource(actor, character, claim),
        van=van_resource,
        scene=SceneResource(
            room_id=safe.room.id or "",
            room_name=safe.room.title,
            visible_characters=[
                entity.name for entity in safe.room.entities if entity.is_character
            ],
        ),
        influences=_influences(actor, character),
        media_available={"image": media.image_available, "video": media.video_available},
    )


def _media_rate_limit(subject: str) -> None:
    now = time.monotonic()
    recent = [
        value
        for value in _MEDIA_REQUESTS.get(subject, [])
        if now - value < MEDIA_REQUEST_WINDOW_SECONDS
    ]
    if len(recent) >= MEDIA_REQUEST_LIMIT:
        raise HTTPException(status_code=429, detail="Studio media request rate limit exceeded")
    recent.append(now)
    _MEDIA_REQUESTS[subject] = recent


def install_play_routes(
    router,
    actor,
    *,
    addon_media: AddonMediaCapability,
    play_websocket_auth: PlayWebSocketAuthCapability,
    **_context,
) -> None:
    @router.get("/characters", response_model=list[CharacterChoice])
    async def characters() -> list[CharacterChoice]:
        choices = []
        for character in (
            actor.world.query().with_all([CharacterComponent, IdentityComponent]).execute_entities()
        ):
            choices.append(
                CharacterChoice(
                    id=str(character.id),
                    name=character.get_component(IdentityComponent).name,
                    claimed=character.has_component(StudioInfluenceClaimComponent),
                )
            )
        return sorted(choices, key=lambda item: (item.name.lower(), item.id))

    @router.post("/claims", response_model=ClaimResource, status_code=201)
    async def claim(body: ClaimRequest, request: Request) -> ClaimResource:
        subject = _subject(request)
        try:
            async with actor._lock:
                character = character_entity(actor, body.character_id)
                before = controller_snapshot(character)
                component = claim_character(actor, body.character_id, subject)
                if controller_snapshot(character) != before:
                    raise RuntimeError("Studio claim changed autonomous controller state")
                return _claim_resource(actor, character, component)
        except (LookupError, TypeError, PermissionError, RuntimeError) as exc:
            raise _claim_error(exc) from exc

    @router.get("/claim", response_model=ClaimResource)
    async def get_claim(request: Request) -> ClaimResource:
        character = _owner_character(actor, request)
        return _claim_resource(
            actor, character, character.get_component(StudioInfluenceClaimComponent)
        )

    @router.delete("/claim", response_model=ClaimResource)
    async def release(request: Request) -> ClaimResource:
        subject = _subject(request)
        async with actor._lock:
            character = _owner_character(actor, request)
            before = controller_snapshot(character)
            component = release_claim(actor, subject)
            if controller_snapshot(character) != before:
                raise RuntimeError("Studio release changed autonomous controller state")
            return _claim_resource(actor, character, component)

    @router.get("/projection", response_model=ProjectionResource)
    async def projection(request: Request) -> ProjectionResource:
        return _projection(actor, _owner_character(actor, request), addon_media)

    @router.get("/influences", response_model=list[InfluenceResource])
    async def influences(request: Request) -> list[InfluenceResource]:
        return _influences(actor, _owner_character(actor, request))

    @router.post("/influences", response_model=InfluenceResource, status_code=201)
    async def influence(body: InfluenceRequest, request: Request) -> InfluenceResource:
        async with actor._lock:
            character = _owner_character(actor, request)
            try:
                entity = add_influence(actor, character, body)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            item = entity.get_component(StudioInfluenceComponent)
        return next(
            resource
            for resource in _influences(actor, character)
            if resource.id == item.influence_id
        )

    @router.delete("/influences/{influence_id}", status_code=204)
    async def delete_influence(influence_id: str, request: Request) -> None:
        async with actor._lock:
            try:
                remove_influence(actor, _owner_character(actor, request), influence_id)
            except LookupError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post("/memories", response_model=MemoryResource, status_code=201)
    async def memory(body: MemoryRequest, request: Request) -> MemoryResource:
        async with actor._lock:
            try:
                entry = add_memory(actor, _owner_character(actor, request), body.text, body.tags)
            except RuntimeError as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc
        return MemoryResource(
            id=entry.id, source=entry.source, created_at_epoch=entry.created_at_epoch
        )

    @router.get("/routes", response_model=list[RouteResource])
    async def routes(request: Request) -> list[RouteResource]:
        return _route_resources(actor, _owner_character(actor, request))

    @router.post("/routes", response_model=RouteResource, status_code=201)
    async def route(body: RouteRequest, request: Request) -> RouteResource:
        async with actor._lock:
            character = _owner_character(actor, request)
            try:
                entity = create_route(actor, character, body)
            except LookupError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            route_id = entity.get_component(StudioRouteComponent).route_id
        return next(item for item in _route_resources(actor, character) if item.id == route_id)

    @router.get("/map", response_model=MapResource)
    async def map_view(request: Request) -> MapResource:
        return _map_resource(actor, _owner_character(actor, request))

    @router.get("/journal", response_model=list[JournalResource])
    async def journal(request: Request) -> list[JournalResource]:
        async with actor._lock:
            character = _owner_character(actor, request)
            _sync_journal_media(actor, character, addon_media)
            return _journal_resources(actor, character)

    @router.post("/journal/reflections", response_model=JournalResource, status_code=201)
    async def reflection(body: ReflectionRequest, request: Request) -> JournalResource:
        async with actor._lock:
            character = _owner_character(actor, request)
            entity = record_journal(
                actor, character, kind="reflection", summary=body.text.strip(), first_person=True
            )
            touch_claim(actor, character)
            moment_id = entity.get_component(StudioJournalMomentComponent).moment_id
        return next(item for item in _journal_resources(actor, character) if item.id == moment_id)

    @router.put("/journal/{moment_id}/pin", response_model=JournalResource)
    async def pin(moment_id: str, request: Request) -> JournalResource:
        async with actor._lock:
            character = _owner_character(actor, request)
            for entity in _owned(actor, character, "journal"):
                item = entity.get_component(StudioJournalMomentComponent)
                if item.moment_id == moment_id:
                    replace_component(entity, replace(item, pinned=True))
                    break
            else:
                raise HTTPException(status_code=404, detail="journal moment does not exist")
        return next(item for item in _journal_resources(actor, character) if item.id == moment_id)

    @router.post("/journal/{moment_id}/media", response_model=MediaJobResource, status_code=202)
    async def media(moment_id: str, body: MediaRequest, request: Request) -> MediaJobResource:
        subject = _subject(request)
        _media_rate_limit(subject)
        character = _owner_character(actor, request)
        moment = next(
            (
                entity
                for entity in _owned(actor, character, "journal")
                if entity.get_component(StudioJournalMomentComponent).moment_id == moment_id
            ),
            None,
        )
        if moment is None:
            raise HTTPException(status_code=404, detail="journal moment does not exist")
        job = (
            await addon_media.request_character_scene_video(
                str(character.id), requested_by=subject, event_id=body.event_id
            )
            if body.kind == "video"
            else await addon_media.request_character_scene_image(
                str(character.id), requested_by=subject, event_id=body.event_id
            )
        )
        if job is None:
            raise HTTPException(status_code=400, detail="character has no scene to illustrate")
        async with actor._lock:
            item = moment.get_component(StudioJournalMomentComponent)
            replace_component(
                moment,
                replace(
                    item,
                    media_job_id=job.id,
                    media_kind=body.kind,
                    media_source_event_id=job.source_event_id,
                    media_status=_normalized_media_status(job.status),
                    media_url=job.url,
                    media_error=job.error or "",
                ),
            )
        return MediaJobResource(**job.__dict__)

    @router.websocket("/observer")
    async def observer(websocket: WebSocket) -> None:
        if not websocket_origin_is_trusted(websocket):
            await websocket.close(code=1008)
            return
        await websocket.accept()
        try:
            frame = await asyncio.wait_for(websocket.receive_json(), PLAYER_WEBSOCKET_AUTH_SECONDS)
            session = play_websocket_auth.authenticate(websocket, frame)
            character = claimed_character(actor, session.subject)
        except (HTTPException, PermissionError, TimeoutError, ValueError, WebSocketDisconnect):
            await websocket.close(code=1008)
            return
        subscription = actor.event_stream.subscribe()
        next_reauth = 0.0
        try:
            await websocket.send_json(
                subscription.frame(
                    actor,
                    {
                        "type": "ready",
                        "data": _projection(actor, character, addon_media).model_dump(mode="json"),
                    },
                )
            )
            while True:
                now = time.monotonic()
                if now >= next_reauth:
                    if not session.reauthorize():
                        await websocket.close(code=1008)
                        return
                    claimed_character(actor, session.subject)
                    next_reauth = now + WEBSOCKET_REAUTHORIZE_SECONDS
                update = await next_player_update(actor, subscription, str(character.id))
                await websocket.send_json(subscription.frame(actor, update))
        except (WebSocketDisconnect, asyncio.CancelledError, PermissionError):
            pass
        finally:
            subscription.close()


def install_admin_routes(router, actor, **_context) -> None:
    @router.delete("/claims/{character_id}", response_model=ClaimResource)
    async def admin_reset(character_id: str) -> ClaimResource:
        try:
            async with actor._lock:
                character = character_entity(actor, character_id)
                before = controller_snapshot(character)
                component = reset_claim(actor, character_id)
                if controller_snapshot(character) != before:
                    raise RuntimeError("Studio reset changed autonomous controller state")
                return _claim_resource(actor, character, component)
        except (LookupError, TypeError, RuntimeError) as exc:
            raise _claim_error(exc) from exc

    @router.get("/generator-config", response_model=GeneratorConfigResource)
    async def generator_config() -> GeneratorConfigResource:
        return GeneratorConfigResource(
            real=RealGeneratorConfig.model_json_schema(),
            fictional_generator="studio-van-waifu-fictional",
            real_generator="studio-van-waifu-real",
        )

    @router.get("/geography/search", response_model=list[LocationSelection])
    async def geography_search(
        query: str,
        nominatim_url: str,
        contact: str,
    ) -> list[LocationSelection]:
        client = OpenMapClient(
            nominatim_url=nominatim_url,
            osrm_url="https://router.project-osrm.org",
            overpass_url="https://overpass-api.de/api/interpreter",
            contact=contact,
        )
        return list(await client.search(query))


__all__ = ["install_admin_routes", "install_play_routes"]
