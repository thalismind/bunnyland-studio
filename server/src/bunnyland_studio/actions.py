"""Autonomous-controller-only Van Waifu action surface."""

from __future__ import annotations

import random
from dataclasses import replace
from uuid import uuid4

from bunnyland.core.actions import ActionArgument, ActionDefinition, ActionEffort, effort_cost
from bunnyland.core.commands import Lane, SubmittedCommand
from bunnyland.core.handlers import (
    HandlerContext,
    HandlerResult,
    planned,
    rejected,
    require_character,
)
from bunnyland.core.mutations import AddEdge, AddEntity, EntityReference, MutationPlan, SetComponent

from .components import (
    StudioBreakdownComponent,
    StudioJournalMomentComponent,
    StudioLocationComponent,
    StudioOwns,
    StudioRouteComponent,
    StudioRouteWaypoint,
    StudioTravelSegmentComponent,
    StudioVanComponent,
)
from .mechanics import (
    BREAKDOWN_COOLDOWN_LEGS,
    OPENING_BREAKDOWN_PROTECTION_LEGS,
    location_by_key,
    owned_van,
    road_distance,
)


class RefuelHandler:
    command_type = "studio-van-refuel"

    def execute(self, ctx: HandlerContext, command: SubmittedCommand) -> HandlerResult:
        _character_id, character, rejection = require_character(ctx, command.character_id)
        if rejection is not None:
            return rejection
        try:
            van_entity = owned_van(ctx.actor, character)
        except LookupError as exc:
            return rejected(str(exc))
        van = van_entity.get_component(StudioVanComponent)
        try:
            location = location_by_key(ctx.actor, van.current_location_id)
        except LookupError as exc:
            return rejected(str(exc))
        if location.get_component(StudioLocationComponent).kind != "fuel":
            return rejected("refueling requires a fuel stop")
        liters = command.payload.get("liters", 20)
        if isinstance(liters, bool) or not isinstance(liters, (int, float)) or liters <= 0:
            return rejected("liters must be a positive number")
        return planned(
            MutationPlan(
                (
                    SetComponent(
                        van_entity.id,
                        replace(van, fuel_liters=min(van.tank_liters, van.fuel_liters + liters)),
                    ),
                )
            )
        )


class RoadsideHandler:
    command_type = "studio-van-call-roadside-assistance"

    def execute(self, ctx: HandlerContext, command: SubmittedCommand) -> HandlerResult:
        _character_id, character, rejection = require_character(ctx, command.character_id)
        if rejection is not None:
            return rejection
        try:
            van_entity = owned_van(ctx.actor, character)
        except LookupError as exc:
            return rejected(str(exc))
        van = van_entity.get_component(StudioVanComponent)
        if not van.broken_down:
            return rejected("the van is not broken down")
        return planned(
            MutationPlan(
                (
                    SetComponent(
                        van_entity.id, replace(van, broken_down=False, active_incident_id="")
                    ),
                )
            )
        )


class ReflectionHandler:
    command_type = "studio-van-write-travel-reflection"

    def execute(self, ctx: HandlerContext, command: SubmittedCommand) -> HandlerResult:
        _character_id, character, rejection = require_character(ctx, command.character_id)
        if rejection is not None:
            return rejection
        text = command.payload.get("text")
        if not isinstance(text, str) or not text.strip():
            return rejected("reflection text is required")
        moment = EntityReference()
        return planned(
            MutationPlan(
                (
                    AddEntity(
                        (
                            StudioJournalMomentComponent(
                                moment_id=uuid4().hex,
                                kind="reflection",
                                summary=text.strip(),
                                occurred_at_epoch=ctx.epoch,
                                first_person=True,
                            ),
                        ),
                        reference=moment,
                    ),
                    AddEdge(character.id, moment, StudioOwns(kind="journal")),
                )
            )
        )


class DriveHandler:
    command_type = "studio-van-drive"

    def execute(self, ctx: HandlerContext, command: SubmittedCommand) -> HandlerResult:
        _character_id, character, rejection = require_character(ctx, command.character_id)
        if rejection is not None:
            return rejection
        try:
            van_entity = owned_van(ctx.actor, character)
        except LookupError as exc:
            return rejected(str(exc))
        van = van_entity.get_component(StudioVanComponent)
        destination = command.payload.get("destination_id")
        if not isinstance(destination, str) or not destination.strip():
            return rejected("destination_id is required")
        try:
            distance = road_distance(ctx.actor, van.current_location_id, destination)
        except LookupError as exc:
            return rejected(str(exc))
        fuel = distance / van.km_per_liter
        if fuel > van.fuel_liters:
            return rejected("insufficient fuel for that road distance")
        if van.broken_down:
            return rejected("the van is broken down")
        completed_legs = van.completed_legs + 1
        cooldown = max(0, van.breakdown_cooldown_legs - 1)
        probability = {"temperamental": 0.08, "fair": 0.04, "dependable": 0.015}[van.reliability]
        breakdown = (
            completed_legs > OPENING_BREAKDOWN_PROTECTION_LEGS
            and cooldown == 0
            and not van.active_incident_id
            and random.Random(f"{ctx.epoch}:{character.id}:{completed_legs}").random() < probability
        )
        incident_id = uuid4().hex if breakdown else ""
        operations = [
            SetComponent(
                van_entity.id,
                replace(
                    van,
                    fuel_liters=van.fuel_liters - fuel,
                    current_location_id=destination,
                    completed_legs=completed_legs,
                    breakdown_cooldown_legs=(BREAKDOWN_COOLDOWN_LEGS if breakdown else cooldown),
                    broken_down=breakdown,
                    active_incident_id=incident_id,
                ),
            )
        ]
        on_route = False
        for route_id in (
            target
            for edge, target in character.get_relationships(StudioOwns)
            if edge.kind == "route" and ctx.world.has_entity(target)
        ):
            route_entity = ctx.world.get_entity(route_id)
            route = route_entity.get_component(StudioRouteComponent)
            if route.status not in {"planned", "active", "paused"}:
                continue
            waypoints = sorted(
                route_entity.get_relationships(StudioRouteWaypoint), key=lambda pair: pair[0].order
            )
            next_index = route.current_waypoint + 1
            if next_index >= len(waypoints):
                continue
            location = ctx.world.get_entity(waypoints[next_index][1])
            if location.get_component(StudioLocationComponent).location_id != destination:
                continue
            on_route = True
            operations.append(
                SetComponent(
                    route_entity.id,
                    replace(
                        route,
                        current_waypoint=next_index,
                        status="completed" if next_index == len(waypoints) - 1 else "active",
                    ),
                )
            )

        segment = EntityReference()
        moment = EntityReference()
        operations.extend(
            (
                AddEntity(
                    (
                        StudioTravelSegmentComponent(
                            segment_id=uuid4().hex,
                            from_location_id=van.current_location_id,
                            to_location_id=destination,
                            distance_km=distance,
                            occurred_at_epoch=ctx.epoch,
                            kind="route" if on_route else "detour",
                        ),
                    ),
                    reference=segment,
                ),
                AddEdge(character.id, segment, StudioOwns(kind="segment")),
                AddEntity(
                    (
                        StudioJournalMomentComponent(
                            moment_id=uuid4().hex,
                            kind="arrival",
                            summary=f"Arrived at {destination} after {distance:.1f} km.",
                            location_id=destination,
                            occurred_at_epoch=ctx.epoch,
                        ),
                    ),
                    reference=moment,
                ),
                AddEdge(character.id, moment, StudioOwns(kind="journal")),
            )
        )
        if breakdown:
            incident = EntityReference()
            breakdown_moment = EntityReference()
            operations.extend(
                (
                    AddEntity(
                        (
                            StudioBreakdownComponent(
                                incident_id=incident_id,
                                location_id=destination,
                                event_seed=ctx.epoch,
                                occurred_at_epoch=ctx.epoch,
                            ),
                        ),
                        reference=incident,
                    ),
                    AddEdge(character.id, incident, StudioOwns(kind="incident")),
                    AddEntity(
                        (
                            StudioJournalMomentComponent(
                                moment_id=uuid4().hex,
                                kind="breakdown",
                                summary="The van broke down after arriving.",
                                location_id=destination,
                                occurred_at_epoch=ctx.epoch,
                            ),
                        ),
                        reference=breakdown_moment,
                    ),
                    AddEdge(character.id, breakdown_moment, StudioOwns(kind="journal")),
                )
            )
        return planned(MutationPlan(tuple(operations)))


ACTION_DEFINITIONS = (
    ActionDefinition(
        command_type="studio-van-drive",
        title="Drive",
        description="Autonomously drive the Studio van to a route destination.",
        lane=Lane.WORLD,
        cost=effort_cost(action=ActionEffort.EXTENDED),
        arguments={
            "destination_id": ActionArgument(kind="string", required=True),
        },
    ),
    ActionDefinition(
        command_type="studio-van-refuel",
        title="Refuel",
        description="Refuel the Studio van at a visible fuel stop.",
        arguments={"liters": ActionArgument(kind="number")},
    ),
    ActionDefinition(
        command_type="studio-van-call-roadside-assistance",
        title="Call roadside assistance",
        description="Call ordinary roadside help after a breakdown.",
    ),
    ActionDefinition(
        command_type="studio-van-write-travel-reflection",
        title="Write travel reflection",
        description="Write a first-person journal reflection.",
        lane=Lane.FOCUS,
        cost=effort_cost(focus=ActionEffort.ROUTINE),
        arguments={"text": ActionArgument(kind="string", required=True)},
    ),
)
ACTION_HANDLERS = (DriveHandler(), RefuelHandler(), RoadsideHandler(), ReflectionHandler())

__all__ = ["ACTION_DEFINITIONS", "ACTION_HANDLERS"]
