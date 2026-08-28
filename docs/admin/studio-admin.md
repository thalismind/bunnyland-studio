# Hosting and administering Bunnyland Studio

Bunnyland Studio combines an out-of-tree Bunnyland server plugin with a static browser client.
It gives one authenticated account an exclusive influence claim over one autonomous main
character while preserving that character's existing controller. Studio works with existing
autonomous characters; Van Waifu is the bundled example story that demonstrates generators,
routes, vehicle mechanics, breakdown narratives, and themed media.

## Security model

Before deployment, keep these boundaries explicit:

- `world:admin` is required for world generation, generator setup, geography search, and
  administrator claim reset.
- `world:play` plus the matching influence claim is required for ongoing Studio use.
- An influence claim does not authorize `/commands`, queued actions, controller assignment,
  Web/Discord/MCP control claims, or any stock direct-control endpoint.
- The plugin's control-claim guard prevents another surface from replacing the autonomous
  controller while Studio ownership is active.
- Claim, release, and reset must leave `ControlledBy` and its generation unchanged.
- Media requests use the narrow addon facade only after owner validation.
- The observer authenticates its first frame and periodically reauthorizes scope, expiry,
  moderation, and ownership.

Treat unexpected controller changes or cross-owner projection access as security issues.

## Install the server plugin

Build a wheel from the repository root:

```bash
uv build --wheel --out-dir dist server
```

Install that wheel into the same Python environment or server image as Bunnyland Server. The
package advertises the `bunnyland.studio` entry point in the `bunnyland.plugins` group.
Enable that plugin ID using the same configured plugin-discovery mechanism as other out-of-tree
addons.

The Studio build requires a Bunnyland Server version containing:

- generation-job `generator_config`;
- the public configured world-agent factory;
- the addon character-scene media facade;
- play-scoped WebSocket authentication; and
- contributed character-control claim guards.

Do not replace these with private imports or raw service access.

## Publish the browser client

Install and build:

```bash
npm ci
npm --prefix web run build
```

Publish `web/dist/` at `/studio/`. Keep the browser and API on the same site so the normal
secure-cookie, CSRF, token, origin, and WebSocket policies apply.

A reverse proxy needs:

- static files and SPA fallback for `/studio/`;
- HTTP forwarding for `/api/`; and
- WebSocket upgrade forwarding for the Studio observer under `/api/v1/play/extensions/`.

Do not place a second authentication proxy in front of only the WebSocket route unless it
preserves Bunnyland's bearer/session credentials and origin checks.

## Configure the Van Waifu example story

Studio itself does not require a special world generator. The included Van Waifu example story
registers:

- `studio-van-waifu-fictional`
- `studio-van-waifu-real`

World creation continues through Bunnyland's normal administrator generation-job endpoint.
Pass the selected generator ID and its typed `generator_config`. The existing job preserves
authorization, confirmation, progress, saving, and atomic world replacement.

### Fictional configuration

```json
{
  "blueprint": {
    "character_name": "Mara Vale",
    "pronouns": "she/her",
    "appearance": "dark curls, crimson road jacket, practical boots",
    "persona": "curious, observant, dryly funny",
    "travel_motivation": "collect stories from overlooked towns",
    "van_name": "Rosefinch",
    "van_description": "a cream camper van with a red stripe and compact darkroom",
    "tank_liters": 60,
    "starting_fuel_liters": 60,
    "km_per_liter": 9,
    "reliability": "fair",
    "anime_direction": "cinematic anime road movie, grounded factual scene"
  },
  "region_name": "Roseglass Highways",
  "town_count": 8,
  "branch_count": 3
}
```

The result is deterministic for the generation seed, connected, and includes a fuel-feasible
opening route with alternate branches for wandering.

### Real-map configuration

Use `GET /v1/admin/extensions/bunnyland.studio/geography/search` during setup to obtain typed
location selections. Then submit explicit origin and destination objects:

```json
{
  "blueprint": {
    "character_name": "Mara Vale",
    "appearance": "dark curls, crimson road jacket, practical boots",
    "persona": "curious, observant, dryly funny",
    "travel_motivation": "follow old highways and local stories",
    "van_name": "Rosefinch",
    "van_description": "a cream camper van with a red stripe"
  },
  "origin": {
    "id": "node:123",
    "name": "Selected origin",
    "point": {"lat": 44.0, "lon": -90.0},
    "osm_type": "node",
    "osm_id": 123
  },
  "destinations": [
    {
      "id": "relation:456",
      "name": "Selected destination",
      "point": {"lat": 45.0, "lon": -91.0},
      "osm_type": "relation",
      "osm_id": 456
    }
  ],
  "nominatim_url": "https://nominatim.openstreetmap.org",
  "osrm_url": "https://router.project-osrm.org",
  "overpass_url": "https://overpass-api.de/api/interpreter",
  "tile_url": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
  "contact": "operator@example.invalid"
}
```

The example IDs are placeholders; always use results returned by the configured search service.

## Real-map service policy

Generation makes bounded, timed calls to:

- Nominatim for place search;
- OSRM for driving distance and time; and
- Overpass for bounded fuel, camp, food, attraction, and repair POIs.

Calls happen during generation, not every simulation tick. Configure an identifiable contact
and user agent. Public Nominatim is unsuitable for bulk or frequent generation; use compatible
self-hosted endpoints for production workloads. Cache results where permitted and do not
fabricate missing real-world services.

Every real-map view must preserve `© OpenStreetMap contributors (ODbL)` attribution and any
additional tile-provider requirements.

References:

- [Nominatim API](https://nominatim.org/release-docs/latest/api/Search/)
- [Nominatim usage policy](https://operations.osmfoundation.org/policies/nominatim/)
- [OSRM API](https://project-osrm.org/docs/)
- [OSMF attribution guidelines](https://osmfoundation.org/wiki/Licence/Attribution_Guidelines)

## Configure narrative and media providers

Breakdown descriptions use the same configured provider, model, endpoint, and credentials as
Bunnyland world generation. The world agent proposes narrative text only. Provider timeout,
unavailability, or invalid output selects a deterministic fallback diagnosis.

Studio media availability follows Bunnyland's image and video services. Requests retain the
character-scene snapshot and add the Van Waifu anime direction through prompt enhancers.
Provider output must not change factual scene contents.

Keep provider credentials server-side. Never send them to the Studio browser or store them in
generator configuration.

## Manage influence claims

The first authenticated player claims one main character. The claim's stable ID, owner subject,
claim epoch, and last-activity epoch persist in the world.

The owner can release it from Studio. If the owner account is unavailable, an administrator can
reset the selected character through:

```text
DELETE /v1/admin/extensions/bunnyland.studio/claims/{character_id}
```

Reset only after verifying the target character and owner. It removes the influence-claim
component but must not change controller assignment or generation. Existing Studio route,
journal, memory, and historical van state remain world data.

## Persistence and backups

Include the normal Bunnyland world snapshot and media stores in backups. Studio state lives in
registered ECS components and edges, including:

- influence claim and influence entities;
- routes and ordered waypoint edges;
- geography, locations, roads, and travel segments;
- van and breakdown incidents;
- journal moments and media job references; and
- Studio-provenance entries in the configured memory store.

Use the same consistent snapshot boundary as Bunnyland Server. Backing up only the web files does
not preserve a journey.

## Operational checks

After installation:

1. Confirm plugin discovery reports `bunnyland.studio`.
2. Confirm both Studio generator IDs appear in the administrator generator catalogue.
3. Generate a small fictional world and open `/studio/`.
4. Claim the main character and verify **Autonomous controller active**.
5. Reconnect with the same account and verify the claim ID is stable.
6. Attempt access with a second account and confirm projection access is denied.
7. Confirm a stock control claim is rejected while the influence claim is active.
8. Add an influence, memory, and route; verify each persists after a save and restart.
9. Exercise the observer reconnect and sequence handling.
10. Request only the media types reported as available.
11. Release or reset the claim and confirm `ControlledBy` is unchanged.
12. For a real map, verify visible OSM/ODbL attribution and configured tile attribution.

Run the repository gate before upgrades:

```bash
scripts/check
```

## Incident response

Privately report authentication bypass, cross-character projection exposure, claim compromise,
raw memory or prompt disclosure, or command authorization through Studio. Preserve relevant
request IDs and versions, but redact bearer tokens, claim identifiers, private memory text,
provider prompts, and player messages before sharing logs.

See the repository
[security policy](https://github.com/thalismind/bunnyland-studio/security/policy) and
Bunnyland Server's canonical supported-release policy.
