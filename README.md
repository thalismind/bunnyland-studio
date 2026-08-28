# Bunnyland Studio

Bunnyland Studio is an out-of-tree addon for autonomous road stories in
[Bunnyland](../bunnyland-server). It installs the `bunnyland.studio` server plugin and a
standalone Preact application served at `/studio/`.

Studio’s claim is deliberately narrow. An authenticated player chooses one main character
and receives an exclusive **influence claim** over Studio projections, influences, memories,
routes, journal moments, and scene media. The claim does not replace `ControlledBy`, does not
create a web controller, and cannot authorize command submission. The existing autonomous
controller remains active.

## What is included

- `server/` — installable Python plugin, typed ECS state and DTOs, Studio route registrars,
  Van Waifu mechanics, media prompt enhancement, and two world generators.
- `web/` — Vite/Preact client with claim setup, dashboard, influence and memory composer,
  itinerary editor, cinematic map, and journal/media views.
- `scripts/` — focused server, web, and combined checks.

The generators are:

- `studio-van-waifu-fictional` — seeded towns, a connected highway loop, local branches,
  fuel/camp/repair/service locations, and a fuel-feasible opening itinerary.
- `studio-van-waifu-real` — explicitly selected OSM locations with OSRM road distance and
  travel-time estimates. Nominatim search and bounded Overpass POI lookup are available only
  during administrator setup.

## Development

The sibling `bunnyland-server` checkout supplies the development dependency:

```bash
scripts/test-server
scripts/test-web
scripts/check
```

Run the client locally with an API proxy:

```bash
cd web
BUNNYLAND_API_PROXY=http://127.0.0.1:8765 npm run dev
```

The production build uses `/studio/` as its Vite base. HTTP and WebSocket traffic stays on the
same origin under `/api/v1/...`.

## Authentication and privacy

Ongoing use requires a `world:play` bearer or same-origin session plus the matching influence
claim. World generation and claim reset require `world:admin`. Studio’s play API contains no
command, action-queue, or controller-assignment endpoint. A contributed core guard prevents
stock Web, Discord, and MCP controller claims while a Studio influence claim is active.

Player projections use Bunnyland’s safe character projection and Studio-owned DTOs. They do
not expose raw ECS component maps, hidden NPC state, private NPC memory, controller prompts, or
model reasoning. Globally authored geography remains visible; live entities still follow the
main character’s normal perception boundary.

See [docs/architecture.md](docs/architecture.md) for route and mechanics contracts and
[docs/operations.md](docs/operations.md) for service configuration and attribution duties.

## License

GNU Affero General Public License v3.0; see [LICENSE](LICENSE).
