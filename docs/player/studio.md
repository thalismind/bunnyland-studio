# Influencing an autonomous character story with Bunnyland Studio

Bunnyland Studio lets one authenticated player follow and influence an autonomous main
character without taking over that character's actions. You can shape priorities, add memories,
observe activity, and preserve important moments while the existing controller continues
deciding what the character actually does.

## Before you begin

You need:

- a Bunnyland account with the `world:play` permission;
- a world with at least one autonomous character;
- the Studio client published at `/studio/`; and
- image or video generation configured only if you want those optional media types.

Studio can claim an existing autonomous character without a special world generator. The
included Van Waifu example story adds a main character, van, geography, and opening itinerary
for a road-focused experience.

## Claim the main character

Open `/studio/`, sign in, and choose **Claim main character**.

This creates an **influence claim**, not a controller claim:

- your account becomes the only account that can read or change Studio state;
- reconnecting with the same account resumes the claim;
- the character's existing controller remains assigned;
- Studio cannot submit actions or commands for the character; and
- normal Web, Discord, and MCP control claims are blocked until you release the influence claim.

Check the dashboard for **Autonomous controller active**. If that message is absent, ask an
administrator to inspect the character's controller before continuing.

If someone else already owns the claim, Studio will not reveal the private projection. The owner
must release it, or an administrator must reset it.

## Read the dashboard

The live dashboard shows only information authorized for the claimed main character:

- the character and influence-claim identity;
- current scene and visible characters;
- van location, fuel, estimated range, reliability band, and breakdown state;
- active influences;
- recent Studio activity; and
- whether image and video generation are available.

The observer connection is sequence-aware. If it reconnects, the client resumes from current
authorized state rather than treating stale frames as new activity. It also periodically checks
that your token and influence claim remain valid.

## Add influences

An influence is context for the autonomous controller, never a command. The character can ignore,
reinterpret, postpone, or conflict with it.

Choose one category:

- **Want** — a desired outcome. A core want also adds an auditable goal.
- **Need** — pressure related to hunger, thirst, fatigue, hygiene, comfort, fun, social contact,
  privacy, or safety. A core need applies one bounded meter change when created.
- **Suggestion** — a soft idea only; suggestions cannot be core.

Then choose low, balanced, or strong pressure. Pressure changes how prominently Studio presents
the fact, not whether the character must obey.

Removing a core want removes only the goal that Studio added. Removing a core need does not undo
its historical meter change.

Good influences describe motivations:

```text
Want, balanced: Find somewhere quiet to watch the meteor shower.
Need, low: Take a proper rest before another long drive.
Suggestion, balanced: Ask the mechanic about scenic roads north.
```

Avoid writing action syntax such as `drive town-4`. Studio deliberately has no command endpoint.

## Contribute a memory

Use the memory composer for facts or recollections the main character should privately remember.
Studio stores the entry in the character's normal private memory collection with
`bunnyland.studio` provenance.

Write memories as information rather than instructions:

```text
At Roseglass Camp, Mara said the old observatory road is beautiful after rain.
```

Memories are private character context. They are not a way to expose another character's hidden
state or model reasoning.

## Use the Van Waifu example story

The remaining route, fuel, breakdown, and travel-journal features in this guide belong to the
bundled Van Waifu example story. They demonstrate how a story pack can build specialized
mechanics and projections on top of Studio's general influence claim.

## Plan a Van Waifu itinerary

Create a route by choosing ordered location IDs and an adherence:

- **Loose** leaves substantial room for wandering.
- **Balanced** is the default travel intention.
- **Strict** emphasizes the planned sequence but still does not force actions.

The map distinguishes intent from fact:

- subdued red segments are future itinerary or available roads;
- bold red segments are completed travel;
- dashed amber segments are detours;
- the van marker shows the latest actual location; and
- playback redraws completed segments in chronological order.

A waypoint advances only when the character actually arrives there. Going elsewhere records a
detour rather than rewriting history. Fuel-range warnings are planning information, not invented
fuel stations.

## Fuel and breakdowns

The autonomous controller can choose Studio's `studio-van-drive`, `studio-van-refuel`,
`studio-van-call-roadside-assistance`, and `studio-van-write-travel-reflection` actions.

- Driving consumes fuel from the persisted road distance.
- Insufficient fuel prevents the drive.
- Refueling requires a mapped fuel stop.
- The opening two legs cannot break down.
- Later breakdowns are rare, seeded, cooldown-bound, and limited to one active incident.
- Roadside assistance recovers the coarse broken-down state.

The configured world-generation model may write the diagnosis, but it cannot create parts or
change fuel, reliability, routes, recovery, or any other mechanical state. A deterministic
fallback explanation is used when the model is unavailable or invalid.

## Journal and media

Studio automatically records factual travel moments such as arrivals, detours, breakdowns, and
recovery. The autonomous character can add first-person travel reflections. You can pin moments
that should remain easy to find.

When a moment offers media:

1. Open the journal moment.
2. Choose image or short video.
3. Submit the request.
4. Follow its generation status in the journal.

Requests are rate-limited and require the matching influence claim. They use the character's
normal factual scene snapshot and Studio's anime road-movie style enhancer. Styling must not add
characters, objects, or events that were not in the scene.

## Release the claim

Choose **Release influence claim** when you are finished. Releasing:

- removes the exclusive Studio ownership;
- does not delete the route, journal, memories, or historical state;
- does not replace or restart the autonomous controller; and
- allows ordinary control surfaces to evaluate the character normally again.

## Troubleshooting

**Matching influence claim is required**

Sign in with the account that established the claim. If that account is unavailable, ask an
administrator to reset the claim.

**Character is claimed by another account**

Only the existing owner can resume or release it. This is expected exclusivity, not a reconnect
failure.

**Media unavailable**

The server has no corresponding image or video provider, or the character has no illustratable
scene. The rest of Studio remains usable.

**Insufficient fuel**

Choose a reachable fuel stop or wait for the autonomous controller to refuel. Studio cannot
enqueue a drive or refuel action for it.

**Map attribution is visible**

Real maps must display OpenStreetMap/ODbL attribution. It is part of the data license and should
not be hidden.

## Privacy boundary

Studio never exposes raw ECS component maps, raw graph queries, private state belonging to
unseen NPCs, controller prompts, provider chain-of-thought, or hidden model reasoning. Visible
characters follow the main character's normal perception. Authored geography can remain visible
because it is route-planning data rather than live NPC knowledge.

For installation, generator configuration, claim reset, and service policy, see the
[Studio administrator guide](../admin/studio-admin.md).
