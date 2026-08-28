# Studio architecture

## Influence claims

`StudioInfluenceClaimComponent` is singleton state on the selected character because one
Studio owner may bind the world’s one main character. Its stable claim ID and authenticated
owner subject persist with the world. Reconnecting with the same account resumes the claim;
another account receives a rejection. Release and administrator reset remove only this
component.

Repeatable state uses entities and directed edges:

- `StudioOwns(kind="influence")` links soft/core wants, needs, and suggestions.
- `StudioOwns(kind="route")` links itinerary entities; ordered `StudioRouteWaypoint` edges
  link authored stops.
- segment, incident, journal, van, and geography ownership use distinct `StudioOwns` kinds.

Studio never modifies the character’s `ControlledBy` relationship or controller generation.
The contributed character-control claim guard supplies eligibility and one rejection reason;
it has no controller mutation authority.

## Van and route mechanics

The autonomous action catalogue includes `studio-van-drive`, `studio-van-refuel`,
`studio-van-call-roadside-assistance`, and `studio-van-write-travel-reflection`. These actions
are available to the character controller through the
normal action catalogue and are intentionally absent from Studio’s HTTP surface.

Driving resolves distance from a persisted road, consumes fuel, records an actual segment and
arrival moment, and advances an itinerary only when the destination is its next waypoint.
Off-itinerary arrivals become detour segments. The first two completed legs are breakdown-safe;
later breakdown checks are seeded, low probability, cooldown-bound, and allow one active
incident.

The simulation decides whether a breakdown occurred. Narrative explanation uses Bunnyland’s
configured world-agent factory and validates a bounded `BreakdownNarrative`. Provider failure,
timeout, or invalid output selects a deterministic built-in narrative. Only diagnosis fields on
the existing incident change; narrative output cannot alter fuel, reliability, cooldown,
routes, actions, or ECS structure.

## HTTP contract

Play routes are under `/v1/play/extensions/bunnyland.studio`:

- `GET /characters`; `POST /claims`; `GET|DELETE /claim`
- `GET /projection`
- `GET|POST /influences`; `DELETE /influences/{id}`
- `POST /memories`
- `GET|POST /routes`; `GET /map`
- `GET /journal`; reflection, pin, and media subresources
- `WS /observer`

Administrator routes are under `/v1/admin/extensions/bunnyland.studio` and provide claim reset,
generator configuration schema, and bounded geography search. World creation itself reuses the
authoritative `/v1/admin/world/generation-jobs` contract with `generator_config`.

Every client response has a named model. Studio media requests pass through the narrow addon
facade only after owner validation. The observer authenticates its first frame through the core
play-scoped helper and periodically reauthorizes token scope, expiry, moderation, and claim
ownership.
