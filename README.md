# Bunnyland Studio

![Bunnyland Studio red-line travel banner](https://raw.githubusercontent.com/thalismind/bunnyland-media/main/vector-style/white-background/banner-addon-studio.png)

**Bunnyland Studio** is an out-of-tree Bunnyland addon for following and influencing one
autonomous main character through a long-running story. It installs the
`bunnyland.studio` server plugin and a standalone Preact application served at
`/studio/`.

Studio is built around an explicit **influence claim**. The owner can see the main
character's private Studio projection, suggest wants and needs, contribute memories,
plan routes, keep a journal, and request scene media. The claim does not replace the
character's `ControlledBy` relationship, does not create a web controller, and cannot
submit direct commands. The autonomous controller stays active and may ignore or
reinterpret every soft influence.

## Highlights

- Exclusive, persistent influence ownership tied to an authenticated Bunnyland account.
- Two world generators for the Van Waifu example story: deterministic fictional geography
  and selected real OpenStreetMap geography.
- Soft and core wants, bounded needs, suggestions, and Studio-provenance memories.
- Intended routes separated from actual travel, including detours and breakdowns.
- A cinematic red-line map with real Leaflet and fictional SVG renderers.
- Fuel, estimated range, coarse reliability, rare seeded breakdowns, and roadside recovery.
- Durable travel journals, first-person reflections, pins, images, and short videos.
- A sequence-aware observer WebSocket with periodic token and claim reauthorization.
- Named request and response DTOs; no raw ECS, controller prompts, hidden reasoning, or
  Studio command-submission endpoint.

## Repository layout

- `server/` — installable Python addon with ECS types, mechanics, prompt fragments,
  generators, typed HTTP routes, media enhancers, and tests.
- `web/` — Vite/Preact client for claim setup, the live dashboard, influences, routes,
  map playback, journal, and media.
- `docs/player/` — player guide for influence claims and the Studio workflow.
- `docs/admin/` — installation, generation, service, security, and claim-reset guide.
- `scripts/` — focused server, web, and combined verification.

## Influence claims are not controller claims

This distinction is the central security contract:

| Influence claim | Controller claim |
| --- | --- |
| Authorizes Studio projection, influences, memories, routes, journal, and media | Authorizes direct character actions |
| Leaves `ControlledBy` and controller generation unchanged | Assigns or replaces a controller |
| Labels prompt context as influence, never commands | Submits commands through normal action surfaces |
| Valid only on Studio routes | Valid on the controlling client surface |
| Blocks competing Web, Discord, and MCP control claims while active | Does not grant Studio ownership |

The first authenticated player to choose an eligible character establishes the claim.
That account can reconnect and resume it. Another account cannot inspect or mutate the
Studio state. The owner can release the claim, and an administrator can reset it without
changing the autonomous controller.

## World generators

Studio's influence claims work with existing autonomous characters and are not tied to a
particular genre, setting, or travel mechanic. As a complete example story, the addon includes
Van Waifu: an autonomous road narrative with a character, van, itinerary, fuel, breakdowns,
journaling, and cinematic media direction.

![Van Waifu example story](https://raw.githubusercontent.com/thalismind/bunnyland-media/main/full-color/banner-addon-studio-van-waifu.png)

The Van Waifu example contributes two generator IDs through Bunnyland's normal
world-generation job:

- `studio-van-waifu-fictional` creates a deterministic connected road network with
  towns, local branches, services, fuel stops, camps, attractions, repair locations, and
  a fuel-feasible opening route.
- `studio-van-waifu-real` accepts explicitly selected OSM places, routes them with OSRM,
  performs bounded Overpass POI discovery, persists coordinates and attribution, and
  reports range gaps instead of inventing real services.

Both example generators use the same Van Waifu blueprint:

- character name, pronouns, appearance, persona, and travel motivation;
- van name, description, tank capacity, starting fuel, efficiency, and reliability;
- an anime road-movie media direction that enhances style without changing scene facts.

Real-map calls happen only during generation. Public Nominatim use requires an identifiable
contact and compliance with its usage policy. Operators can replace Nominatim, OSRM,
Overpass, and tile endpoints with compatible self-hosted services.

## Player workflow

1. Sign in to the same-origin Studio site with an account that has `world:play`.
2. Select **Claim main character**. Reconnecting with the same account resumes the claim.
3. Confirm the dashboard says **Autonomous controller active**.
4. Add influences or Studio memories. Suggestions are always soft; core needs are bounded.
5. Create an itinerary. The route is intent, not queued movement.
6. Follow actual arrivals, detours, fuel state, breakdowns, and recovery on the map.
7. Read or pin journal moments, add first-person reflections, and request available media.
8. Release the influence claim when the character should become claimable elsewhere.

See the complete [player guide](docs/player/studio.md).

## Van and route mechanics

The plugin contributes `drive`, `refuel`, `call-roadside-assistance`, and
`write-travel-reflection` to the autonomous action catalogue. They are available to the
character's controller, not to Studio's influence API.

Driving resolves a persisted road distance and consumes fuel. An intended waypoint advances
only after the character actually arrives. Other arrivals become detours. The first two legs
are protected from breakdowns; later checks use a low seeded probability, one active incident,
and a hard cooldown.

The simulation alone decides whether a breakdown occurs. Bunnyland's configured world agent
may describe a bounded diagnosis, symptoms, explanation, and broad recommendation. Invalid or
unavailable model output falls back to a deterministic built-in explanation. Narrative output
cannot change fuel, reliability, routes, recovery time, actions, or ECS structure.

## HTTP and WebSocket surface

Play routes live under `/v1/play/extensions/bunnyland.studio`:

- `GET /characters`
- `POST /claims`; `GET|DELETE /claim`
- `GET /projection`
- `GET|POST /influences`; `DELETE /influences/{id}`
- `POST /memories`
- `GET|POST /routes`; `GET /map`
- `GET /journal`; reflection, pin, and media subresources
- `WS /observer`

Administrator routes live under `/v1/admin/extensions/bunnyland.studio`:

- `DELETE /claims/{character_id}`
- `GET /generator-config`
- `GET /geography/search`

World creation remains on Bunnyland's authoritative
`/v1/admin/world/generation-jobs` endpoint, using `generator_config`. Studio does not
expose a command, queued-action, controller-assignment, raw graph-query, or raw ECS endpoint.

## Installation

Studio requires the Bunnyland Server extension points shipped alongside this addon.

Build the Python wheel:

```bash
uv build --wheel --out-dir dist server
```

Install the wheel into the same Python environment as Bunnyland Server. Plugin discovery
loads the `bunnyland.studio` entry point automatically when the configured plugin set
includes it.

Build the browser client:

```bash
npm ci
npm --prefix web run build
```

Publish `web/dist/` at `/studio/`. The reverse proxy must forward same-origin `/api/`
HTTP and WebSocket traffic to Bunnyland Server and provide SPA fallback to
`/studio/index.html`.

The included container layers can be built with:

```bash
docker build -f Dockerfile.server -t bunnyland-studio-server .
docker build -f Dockerfile.web -t bunnyland-studio-web .
```

For service configuration, generation examples, security boundaries, and deployment checks,
see the complete [administrator guide](docs/admin/studio-admin.md) and
[operations notes](docs/operations.md).

## Development and verification

The sibling `bunnyland-server` checkout supplies the development runtime:

```bash
scripts/test-server
scripts/test-web
scripts/check
```

Run the browser locally with an API proxy:

```bash
cd web
BUNNYLAND_API_PROXY=http://127.0.0.1:8765 npm run dev
```

`scripts/check` runs Python tests and Ruff checks, builds the TypeScript client, runs
contract tests, exercises the Playwright claim/travel/breakdown/media flow, rejects Python
`Any` and TypeScript `any`, and checks the Git diff.

## Authentication, privacy, and media

- Ongoing Studio use requires `world:play` and the matching influence claim.
- Generator setup and claim reset require `world:admin`.
- The observer authenticates its first frame and periodically rechecks scope, expiry,
  moderation, and ownership.
- Player projections reuse Bunnyland's safe character projection plus Studio-owned DTOs.
- Hidden NPC state, raw memories, controller prompts, provider reasoning, and unrelated live
  events are not exposed.
- Media requests use Bunnyland's narrow character-scene facade after claim validation and
  retain the normal factual scene snapshot.
- Globally authored geography may be visible; live characters and events continue to follow
  the main character's perception boundary.

Report security issues privately as described in [SECURITY.md](SECURITY.md).

## OpenStreetMap attribution

Real-map worlds preserve and display `© OpenStreetMap contributors (ODbL)`. Do not remove
that attribution when changing the tile provider or embedding Studio elsewhere. Additional
provider attribution may also be required.

- [Nominatim search API](https://nominatim.org/release-docs/latest/api/Search/)
- [Nominatim usage policy](https://operations.osmfoundation.org/policies/nominatim/)
- [OSRM API](https://project-osrm.org/docs/)
- [OSMF attribution guidelines](https://osmfoundation.org/wiki/Licence/Attribution_Guidelines)

## Project policies

- [Contributing](CONTRIBUTING.md)
- [Code of Conduct](CODE_OF_CONDUCT.md)
- [Security Policy](SECURITY.md)
- [Architecture](docs/architecture.md)

## License

GNU Affero General Public License v3.0 or later. See [LICENSE](LICENSE).
