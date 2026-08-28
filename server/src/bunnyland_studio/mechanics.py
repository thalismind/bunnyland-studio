"""Influence claims, prompt facts, routes, van state, and journal mechanics."""

from __future__ import annotations

import random
from dataclasses import replace
from uuid import uuid4

from bunnyland.core import CharacterComponent, MemoryProfileComponent
from bunnyland.core.ecs import parse_entity_id, replace_component, spawn_entity
from bunnyland.core.edges import ControlledBy
from bunnyland.foundation.meters.mechanics import changed
from bunnyland.foundation.needs.mechanics import (
    ComfortNeedComponent,
    FatigueComponent,
    FunNeedComponent,
    HungerComponent,
    HygieneComponent,
    PrivacyNeedComponent,
    SafetyNeedComponent,
    SocialNeedComponent,
    ThirstComponent,
)
from bunnyland.foundation.persona.mechanics import GoalComponent
from bunnyland.prompts import PromptFact
from bunnyland.server.worldgen import build_world_agent
from bunnyland.worldgen import GenOptions
from bunnyland.worldgen.recursive_builder import RoomNodeProposal
from pydantic import ValidationError
from relics import Entity, EntityId

from .components import (
    StudioBreakdownComponent,
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
from .models import BreakdownNarrative, InfluenceRequest, RouteRequest

CLAIM_REJECTION = "character has an active Studio influence claim"
OPENING_BREAKDOWN_PROTECTION_LEGS = 2
BREAKDOWN_COOLDOWN_LEGS = 4

NEED_COMPONENTS = {
    "hunger": HungerComponent,
    "thirst": ThirstComponent,
    "fatigue": FatigueComponent,
    "hygiene": HygieneComponent,
    "comfort": ComfortNeedComponent,
    "fun": FunNeedComponent,
    "social": SocialNeedComponent,
    "privacy": PrivacyNeedComponent,
    "safety": SafetyNeedComponent,
}


class StudioControlClaimGuard:
    id = "bunnyland.studio.influence-claim"

    def rejection_reason(self, actor, character) -> str | None:
        del actor
        return CLAIM_REJECTION if character.has_component(StudioInfluenceClaimComponent) else None


def character_entity(actor, character_id: str) -> Entity:
    parsed = parse_entity_id(character_id)
    if parsed is None or not actor.world.has_entity(parsed):
        raise LookupError("character does not exist")
    character = actor.world.get_entity(parsed)
    if not character.has_component(CharacterComponent):
        raise TypeError("entity is not a character")
    return character


def claim_character(actor, character_id: str, owner_subject: str) -> StudioInfluenceClaimComponent:
    character = character_entity(actor, character_id)
    existing = (
        character.get_component(StudioInfluenceClaimComponent)
        if character.has_component(StudioInfluenceClaimComponent)
        else None
    )
    if existing is not None:
        if existing.owner_subject != owner_subject:
            raise PermissionError("main character is claimed by another account")
        resumed = replace(existing, last_activity_epoch=actor.epoch)
        replace_component(character, resumed)
        return resumed
    claimed = list(actor.world.query().with_all([StudioInfluenceClaimComponent]).execute_entities())
    if claimed:
        raise RuntimeError("a Studio main character is already claimed")
    component = StudioInfluenceClaimComponent(
        claim_id=uuid4().hex,
        owner_subject=owner_subject,
        claimed_at_epoch=actor.epoch,
        last_activity_epoch=actor.epoch,
    )
    character.add_component(component)
    return component


def claimed_character(actor, owner_subject: str) -> Entity:
    for character in (
        actor.world.query()
        .with_all([CharacterComponent, StudioInfluenceClaimComponent])
        .execute_entities()
    ):
        claim = character.get_component(StudioInfluenceClaimComponent)
        if claim.owner_subject == owner_subject:
            return character
    raise PermissionError("matching influence claim is required")


def touch_claim(actor, character: Entity) -> StudioInfluenceClaimComponent:
    claim = character.get_component(StudioInfluenceClaimComponent)
    updated = replace(claim, last_activity_epoch=actor.epoch)
    replace_component(character, updated)
    return updated


def release_claim(actor, owner_subject: str) -> StudioInfluenceClaimComponent:
    character = claimed_character(actor, owner_subject)
    claim = character.get_component(StudioInfluenceClaimComponent)
    character.remove_component(StudioInfluenceClaimComponent)
    return claim


def reset_claim(actor, character_id: str) -> StudioInfluenceClaimComponent:
    character = character_entity(actor, character_id)
    if not character.has_component(StudioInfluenceClaimComponent):
        raise LookupError("character has no influence claim")
    claim = character.get_component(StudioInfluenceClaimComponent)
    character.remove_component(StudioInfluenceClaimComponent)
    return claim


def controller_snapshot(character: Entity) -> tuple[tuple[str, int], ...]:
    return tuple(
        (str(target), edge.generation) for edge, target in character.get_relationships(ControlledBy)
    )


def _owned(character: Entity, kind: str) -> list[EntityId]:
    return [target for edge, target in character.get_relationships(StudioOwns) if edge.kind == kind]


def add_influence(actor, character: Entity, request: InfluenceRequest) -> Entity:
    if request.category == "suggestion" and request.strength == "core":
        raise ValueError("suggestions are soft-only")
    if request.strength == "core" and request.category == "need" and not request.need:
        raise ValueError("core needs require a supported need")
    influence_id = uuid4().hex
    goal_text = (
        f"[Studio:{influence_id}] {request.text}"
        if request.strength == "core" and request.category == "want"
        else ""
    )
    influence = spawn_entity(
        actor.world,
        [
            StudioInfluenceComponent(
                influence_id=influence_id,
                category=request.category,
                strength=request.strength,
                pressure=request.pressure,
                text=request.text.strip(),
                need=request.need,
                need_delta=request.need_delta,
                goal_text=goal_text,
                created_at_epoch=actor.epoch,
            )
        ],
    )
    character.add_relationship(StudioOwns(kind="influence"), influence.id)
    if goal_text:
        goals = (
            character.get_component(GoalComponent)
            if character.has_component(GoalComponent)
            else GoalComponent()
        )
        updated = replace(goals, active_goals=(*goals.active_goals, goal_text))
        if character.has_component(GoalComponent):
            replace_component(character, updated)
        else:
            character.add_component(updated)
    if request.strength == "core" and request.category == "need":
        component_type = NEED_COMPONENTS[request.need]
        component = (
            character.get_component(component_type)
            if character.has_component(component_type)
            else component_type()
        )
        updated = replace(component, meter=changed(component.meter, request.need_delta))
        if character.has_component(component_type):
            replace_component(character, updated)
        else:
            character.add_component(updated)
    touch_claim(actor, character)
    return influence


def remove_influence(actor, character: Entity, influence_id: str) -> None:
    for target in _owned(character, "influence"):
        if not actor.world.has_entity(target):
            continue
        entity = actor.world.get_entity(target)
        component = entity.get_component(StudioInfluenceComponent)
        if component.influence_id != influence_id:
            continue
        if component.goal_text and character.has_component(GoalComponent):
            goals = character.get_component(GoalComponent)
            replace_component(
                character,
                replace(
                    goals,
                    active_goals=tuple(
                        goal for goal in goals.active_goals if goal != component.goal_text
                    ),
                ),
            )
        actor.world.remove(target)
        touch_claim(actor, character)
        return
    raise LookupError("influence does not exist")


def influence_fragments(world, character) -> list[PromptFact]:
    if not character.has_component(StudioInfluenceClaimComponent):
        return []
    pressure_detail = {"strong": 5, "balanced": 10, "low": 20}
    facts: list[PromptFact] = []
    for target in _owned(character, "influence"):
        if not world.has_entity(target):
            continue
        influence = world.get_entity(target).get_component(StudioInfluenceComponent)
        facts.append(
            PromptFact(
                key=f"studio.influence.{influence.influence_id}",
                text=(
                    f"Influence ({influence.pressure} {influence.category}, not a command): "
                    f"{influence.text}. You may ignore or reinterpret it."
                ),
                detail=pressure_detail[influence.pressure],
            )
        )
    return sorted(facts, key=lambda fact: fact.key)


def route_fragments(world, character) -> list[PromptFact]:
    if not character.has_component(StudioInfluenceClaimComponent):
        return []
    facts: list[PromptFact] = []
    for target in _owned(character, "route"):
        if not world.has_entity(target):
            continue
        route_entity = world.get_entity(target)
        route = route_entity.get_component(StudioRouteComponent)
        if route.status == "completed":
            continue
        waypoints = sorted(
            route_entity.get_relationships(StudioRouteWaypoint), key=lambda pair: pair[0].order
        )
        remaining = [
            world.get_entity(location_id).get_component(StudioLocationComponent).name
            for _edge, location_id in waypoints[route.current_waypoint + 1 :]
            if world.has_entity(location_id)
        ]
        if not remaining:
            continue
        facts.append(
            PromptFact(
                key=f"studio.route.{route.route_id}",
                text=(
                    f"Route influence ({route.adherence}, not a command): the intended next stop "
                    f"is {remaining[0]}; later stops are {', '.join(remaining[1:]) or 'none'}. "
                    "Actual travel, detours, pauses, and getting lost remain your decisions."
                ),
                detail=8,
            )
        )
    return sorted(facts, key=lambda fact: fact.key)


def van_fragments(world, character) -> list[PromptFact]:
    facts: list[PromptFact] = []
    for target in _owned(character, "van"):
        if not world.has_entity(target):
            continue
        van = world.get_entity(target).get_component(StudioVanComponent)
        condition = "broken down" if van.broken_down else van.reliability
        facts.append(
            PromptFact(
                key="studio.van.state",
                text=(
                    f"Your mobile home {van.name} is at {van.current_location_id}, has "
                    f"{van.fuel_liters:.1f} L fuel (about "
                    f"{van.fuel_liters * van.km_per_liter:.1f} km), and is {condition}."
                ),
                detail=6,
            )
        )
        break
    return facts


def add_memory(actor, character: Entity, text: str, tags: tuple[str, ...]):
    if actor.memory_store is None:
        raise RuntimeError("memory is not configured")
    if not character.has_component(MemoryProfileComponent):
        character.add_component(
            MemoryProfileComponent(vector_collection=f"character-{character.id}")
        )
    collection = character.get_component(MemoryProfileComponent).vector_collection
    entry = actor.memory_store.add(
        collection,
        text=text.strip(),
        tags=tuple(dict.fromkeys((*tags, "studio"))),
        created_at_epoch=actor.epoch,
        source="bunnyland.studio",
    )
    touch_claim(actor, character)
    return entry


def create_route(actor, character: Entity, request: RouteRequest) -> Entity:
    route = spawn_entity(
        actor.world,
        [
            StudioRouteComponent(
                route_id=uuid4().hex,
                title=request.title.strip(),
                adherence=request.adherence,
                status="active",
                created_at_epoch=actor.epoch,
            )
        ],
    )
    for order, waypoint in enumerate(request.waypoints):
        location = location_by_key(actor, waypoint.location_id)
        route.add_relationship(StudioRouteWaypoint(order=order), location.id)
    character.add_relationship(StudioOwns(kind="route"), route.id)
    touch_claim(actor, character)
    return route


def location_by_key(actor, location_id: str) -> Entity:
    for entity in actor.world.query().with_all([StudioLocationComponent]).execute_entities():
        if entity.get_component(StudioLocationComponent).location_id == location_id:
            return entity
    raise LookupError("location does not exist")


def owned_van(actor, character: Entity) -> Entity:
    for target in _owned(character, "van"):
        if actor.world.has_entity(target):
            return actor.world.get_entity(target)
    raise LookupError("main character has no Studio van")


def road_distance(actor, source: str, destination: str) -> float:
    for road in actor.world.query().with_all([StudioRoadComponent]).execute_entities():
        component = road.get_component(StudioRoadComponent)
        if {component.from_location_id, component.to_location_id} == {source, destination}:
            return component.distance_km
    raise LookupError("no road connects those locations")


def record_journal(
    actor,
    character: Entity,
    *,
    kind: str,
    summary: str,
    location_id: str = "",
    first_person: bool = False,
) -> Entity:
    moment = spawn_entity(
        actor.world,
        [
            StudioJournalMomentComponent(
                moment_id=uuid4().hex,
                kind=kind,
                summary=summary,
                location_id=location_id,
                occurred_at_epoch=actor.epoch,
                first_person=first_person,
            )
        ],
    )
    character.add_relationship(StudioOwns(kind="journal"), moment.id)
    return moment


def drive_van(
    actor, character: Entity, destination_id: str, event_seed: int
) -> tuple[Entity, Entity | None]:
    van_entity = owned_van(actor, character)
    van = van_entity.get_component(StudioVanComponent)
    if van.broken_down:
        raise RuntimeError("the van is broken down")
    distance = road_distance(actor, van.current_location_id, destination_id)
    fuel_used = distance / van.km_per_liter
    if fuel_used > van.fuel_liters:
        raise RuntimeError("insufficient fuel for that road distance")
    cooldown = max(0, van.breakdown_cooldown_legs - 1)
    completed = van.completed_legs + 1
    probability = {"temperamental": 0.08, "fair": 0.04, "dependable": 0.015}[van.reliability]
    breakdown = (
        completed > OPENING_BREAKDOWN_PROTECTION_LEGS
        and cooldown == 0
        and not van.active_incident_id
        and random.Random(f"{event_seed}:{completed}").random() < probability
    )
    incident_id = uuid4().hex if breakdown else ""
    replace_component(
        van_entity,
        replace(
            van,
            fuel_liters=van.fuel_liters - fuel_used,
            current_location_id=destination_id,
            completed_legs=completed,
            breakdown_cooldown_legs=(BREAKDOWN_COOLDOWN_LEGS if breakdown else cooldown),
            broken_down=breakdown,
            active_incident_id=incident_id,
        ),
    )
    on_route = False
    for route_id in _owned(character, "route"):
        if not actor.world.has_entity(route_id):
            continue
        route_entity = actor.world.get_entity(route_id)
        route = route_entity.get_component(StudioRouteComponent)
        if route.status not in {"planned", "active", "paused"}:
            continue
        waypoints = sorted(
            route_entity.get_relationships(StudioRouteWaypoint), key=lambda pair: pair[0].order
        )
        next_index = route.current_waypoint + 1
        if next_index >= len(waypoints):
            continue
        next_location = actor.world.get_entity(waypoints[next_index][1]).get_component(
            StudioLocationComponent
        )
        if next_location.location_id != destination_id:
            continue
        on_route = True
        replace_component(
            route_entity,
            replace(
                route,
                current_waypoint=next_index,
                status="completed" if next_index == len(waypoints) - 1 else "active",
            ),
        )
    segment = spawn_entity(
        actor.world,
        [
            StudioTravelSegmentComponent(
                segment_id=uuid4().hex,
                from_location_id=van.current_location_id,
                to_location_id=destination_id,
                distance_km=distance,
                occurred_at_epoch=actor.epoch,
                kind="route" if on_route else "detour",
            )
        ],
    )
    character.add_relationship(StudioOwns(kind="segment"), segment.id)
    record_journal(
        actor,
        character,
        kind="arrival",
        summary=f"Arrived at {destination_id} after {distance:.1f} km.",
        location_id=destination_id,
    )
    incident = None
    if breakdown:
        incident = spawn_entity(
            actor.world,
            [
                StudioBreakdownComponent(
                    incident_id=incident_id,
                    location_id=destination_id,
                    event_seed=event_seed,
                    occurred_at_epoch=actor.epoch,
                )
            ],
        )
        character.add_relationship(StudioOwns(kind="incident"), incident.id)
        record_journal(
            actor,
            character,
            kind="breakdown",
            summary="The van broke down after arriving.",
            location_id=destination_id,
        )
    return segment, incident


def refuel_van(actor, character: Entity, liters: float) -> StudioVanComponent:
    van_entity = owned_van(actor, character)
    van = van_entity.get_component(StudioVanComponent)
    if liters <= 0:
        raise ValueError("liters must be a positive number")
    location = location_by_key(actor, van.current_location_id)
    if location.get_component(StudioLocationComponent).kind != "fuel":
        raise RuntimeError("refueling requires a fuel stop")
    updated = replace(van, fuel_liters=min(van.tank_liters, van.fuel_liters + liters))
    replace_component(van_entity, updated)
    return updated


def recover_van(actor, character: Entity) -> StudioVanComponent:
    van_entity = owned_van(actor, character)
    van = van_entity.get_component(StudioVanComponent)
    if not van.broken_down:
        raise RuntimeError("the van is not broken down")
    updated = replace(van, broken_down=False, active_incident_id="")
    replace_component(van_entity, updated)
    record_journal(
        actor,
        character,
        kind="note",
        summary="Roadside assistance got the van moving again.",
        location_id=van.current_location_id,
    )
    return updated


FALLBACK_BREAKDOWNS = (
    BreakdownNarrative(
        diagnosis="A tired alternator belt is slipping",
        symptoms=("a sharp squeal", "the charging light flickered"),
        explanation="Heat and recent mileage left the aging belt unable to hold tension.",
        recommendation="Have a mechanic inspect the belt and charging system.",
    ),
    BreakdownNarrative(
        diagnosis="The cooling system lost pressure",
        symptoms=("a sweet smell", "steam after stopping"),
        explanation="A small hose leak became noticeable after the long drive.",
        recommendation="Let the engine cool and have a mechanic pressure-test the system.",
    ),
)


async def explain_breakdown(
    actor,
    incident: Entity,
    *,
    van: StudioVanComponent,
    options: GenOptions,
) -> BreakdownNarrative:
    component = incident.get_component(StudioBreakdownComponent)
    source = "world-agent"
    try:
        agent = build_world_agent(options)
        proposal = await agent.propose_event(
            RoomNodeProposal(
                key=component.location_id,
                title=component.location_id,
                biome="roadside",
                description="A visible roadside stop after recent travel.",
            ),
            prompt=(
                "Purely narrate one plausible broad van breakdown cause. "
                f"Van: {van.description}; reliability: {van.reliability}; "
                f"fuel: {van.fuel_liters:.1f} L; seed: {component.event_seed}."
            ),
            known_rooms={component.location_id: "current roadside location"},
            schema_context="Do not propose commands, entities, parts, fuel, timing, or mechanics.",
        )
        narrative = BreakdownNarrative(
            diagnosis=proposal.title,
            symptoms=(proposal.kind.replace("-", " "),),
            explanation=proposal.description or proposal.title,
            recommendation="Ask a nearby mechanic for a broad inspection.",
        )
    except (RuntimeError, TimeoutError, ValueError, ValidationError, TypeError):
        source = "fallback"
        narrative = FALLBACK_BREAKDOWNS[component.event_seed % len(FALLBACK_BREAKDOWNS)]
    replace_component(
        incident,
        replace(
            component,
            diagnosis=narrative.diagnosis,
            symptoms=narrative.symptoms,
            explanation=narrative.explanation,
            recommendation=narrative.recommendation,
            narrative_source=source,
        ),
    )
    return narrative


__all__ = [name for name in globals() if not name.startswith("_")]
