"""Out-of-tree Bunnyland Studio plugin entrypoint."""

from __future__ import annotations

from bunnyland.plugins import (
    CommandContribution,
    ContentContribution,
    DependencyContribution,
    EcsContribution,
    HttpContribution,
    HttpZone,
    Plugin,
    PluginPlacement,
    PolicyContribution,
    RuntimeContribution,
)

from .actions import ACTION_DEFINITIONS, ACTION_HANDLERS
from .api import install_admin_routes, install_play_routes
from .components import (
    StudioBreakdownComponent,
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
from .events import (
    StudioInfluenceClaimedEvent,
    StudioInfluenceReleasedEvent,
    VanBreakdownExplainedEvent,
    VanBreakdownOccurredEvent,
)
from .generators import FICTIONAL_GENERATOR, REAL_GENERATOR
from .mechanics import (
    StudioControlClaimGuard,
    influence_fragments,
    route_fragments,
    van_fragments,
)
from .media import StudioAnimeEnhancer

PLUGIN_ID = "bunnyland.studio"
PLUGIN_VERSION = "0.1.0"


def plugin() -> Plugin:
    anime = StudioAnimeEnhancer()
    return Plugin(
        id=PLUGIN_ID,
        name="Bunnyland Studio",
        version=PLUGIN_VERSION,
        placement=PluginPlacement.ADDON,
        default_enabled=True,
        dependencies=DependencyContribution(
            requires=("bunnyland.core_verbs", "bunnyland.lifesim", "bunnyland.worldgen"),
            recommends=("bunnyland.memory", "bunnyland.media", "bunnyland.storyteller"),
        ),
        ecs=EcsContribution(
            components=(
                StudioInfluenceClaimComponent,
                StudioInfluenceComponent,
                StudioRouteComponent,
                StudioLocationComponent,
                StudioRoadComponent,
                StudioVanComponent,
                StudioTravelSegmentComponent,
                StudioBreakdownComponent,
                StudioJournalMomentComponent,
                StudioGeographyComponent,
            ),
            edges=(StudioOwns, StudioRouteWaypoint),
        ),
        commands=CommandContribution(
            action_handlers=ACTION_HANDLERS,
            action_definitions=ACTION_DEFINITIONS,
            typed_events=(
                StudioInfluenceClaimedEvent,
                StudioInfluenceReleasedEvent,
                VanBreakdownOccurredEvent,
                VanBreakdownExplainedEvent,
            ),
        ),
        runtime=RuntimeContribution(
            http=(
                HttpContribution(zone=HttpZone.PLAY, registrars=(install_play_routes,)),
                HttpContribution(zone=HttpZone.ADMIN, registrars=(install_admin_routes,)),
            )
        ),
        content=ContentContribution(
            world_generators=(REAL_GENERATOR, FICTIONAL_GENERATOR),
            prompt_fragments=(influence_fragments, route_fragments, van_fragments),
            image_prompt_enhancers=(anime,),
            video_prompt_enhancers=(anime,),
        ),
        policy=PolicyContribution(character_control_claim_guards=(StudioControlClaimGuard(),)),
    )


def bunnyland_plugins() -> list[Plugin]:
    return [plugin()]


__all__ = ["PLUGIN_ID", "PLUGIN_VERSION", "bunnyland_plugins", "plugin"]
