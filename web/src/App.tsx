import { useEffect, useMemo, useState } from 'preact/hooks';

import { StudioApi } from './api';
import { JourneyMap } from './JourneyMap';
import type {
  CharacterChoice,
  JournalResource,
  MapResource,
  ProjectionResource,
  RouteResource,
} from './types';

type Workspace = {
  projection: ProjectionResource;
  map: MapResource;
  routes: RouteResource[];
  journal: JournalResource[];
};

const errorMessage = (error: unknown): string =>
  error instanceof Error ? error.message : 'Studio request failed';

function SignIn({ onSignIn }: { onSignIn: (username: string, password: string) => Promise<void> }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  return (
    <main class="welcome">
      <p class="eyebrow">Autonomous story studio</p>
      <h1>Bunnyland Studio</h1>
      <p>
        Choose one main character, shape what matters to them, and watch the story unfold. The
        autonomous controller remains active; Studio influences are never direct commands.
      </p>
      <form
        class="auth-card"
        onSubmit={event => {
          event.preventDefault();
          setError('');
          void onSignIn(username.trim(), password).catch(problem => setError(errorMessage(problem)));
        }}
      >
        <label for="studio-username">Username</label>
        <input
          id="studio-username"
          autoComplete="username"
          value={username}
          onInput={event => setUsername(event.currentTarget.value)}
          required
        />
        <label for="studio-password">Password</label>
        <input
          id="studio-password"
          type="password"
          autoComplete="current-password"
          value={password}
          onInput={event => setPassword(event.currentTarget.value)}
          required
        />
        <button type="submit">Enter Studio</button>
        {error && <output class="warning">{error}</output>}
      </form>
    </main>
  );
}

function ClaimScreen({
  api,
  choices,
  onClaim,
  reload,
}: {
  api: StudioApi;
  choices: CharacterChoice[];
  onClaim: (id: string) => Promise<void>;
  reload: () => Promise<void>;
}) {
  const [selected, setSelected] = useState(choices.find(choice => !choice.claimed)?.id ?? '');
  const [setup, setSetup] = useState(
    JSON.stringify(
      {
        blueprint: {
          character_name: 'Mira',
          pronouns: 'she/her',
          appearance: 'short black hair, red road jacket',
          persona: 'curious, practical, and kind',
          travel_motivation: 'find overlooked roadside stories',
          van_name: 'Kitsune',
          van_description: 'a compact cream camper van with a red stripe',
          anime_direction: 'cinematic anime road movie, grounded factual scene',
        },
        region_name: 'Roseglass Highways',
        town_count: 8,
        branch_count: 3,
      },
      null,
      2,
    ),
  );
  const [setupMessage, setSetupMessage] = useState('');
  return (
    <main class="welcome">
      <p class="eyebrow">Influence claim</p>
      <h1>Claim main character</h1>
      <p>
        This exclusive claim opens private observation, memories, routes, journaling, and media.
        It does not replace the character’s autonomous controller.
      </p>
      <form
        class="auth-card"
        onSubmit={event => {
          event.preventDefault();
          if (selected) void onClaim(selected);
        }}
      >
        <label for="main-character">Main character</label>
        <select
          id="main-character"
          value={selected}
          onChange={event => setSelected(event.currentTarget.value)}
        >
          <option value="">Choose a character</option>
          {choices.map(choice => (
            <option key={choice.id} value={choice.id} disabled={choice.claimed}>
              {choice.name}{choice.claimed ? ' — claimed' : ''}
            </option>
          ))}
        </select>
        <button type="submit" disabled={!selected}>Claim main character</button>
      </form>
      <details class="auth-card admin-setup">
        <summary>Administrator world setup</summary>
        <p>
          Requires <code>world:admin</code>. Generation uses the server’s confirmed, atomic world
          job.
        </p>
        <form
          onSubmit={event => {
            event.preventDefault();
            try {
              const config = JSON.parse(setup) as unknown;
              void api
                .generate('studio-van-waifu-fictional', config)
                .then(() => reload())
                .then(() => setSetupMessage('Generation job accepted'))
                .catch(error => setSetupMessage(errorMessage(error)));
            } catch (error) {
              setSetupMessage(errorMessage(error));
            }
          }}
        >
          <label for="generator-config">Fictional Van Waifu configuration</label>
          <textarea
            id="generator-config"
            class="config-editor"
            value={setup}
            onInput={event => setSetup(event.currentTarget.value)}
          />
          <button type="submit">Generate Studio world</button>
          <output>{setupMessage}</output>
        </form>
      </details>
    </main>
  );
}

function Composer({ api, refresh }: { api: StudioApi; refresh: () => Promise<void> }) {
  const [mode, setMode] = useState<'influence' | 'memory'>('influence');
  const [text, setText] = useState('');
  const [category, setCategory] = useState<'want' | 'need' | 'suggestion'>('suggestion');
  const [strength, setStrength] = useState<'soft' | 'core'>('soft');
  const [message, setMessage] = useState('');
  return (
    <section class="panel composer">
      <div class="tabs">
        <button class={mode === 'influence' ? 'active' : ''} onClick={() => setMode('influence')}>
          Influence
        </button>
        <button class={mode === 'memory' ? 'active' : ''} onClick={() => setMode('memory')}>
          Memory
        </button>
      </div>
      <h2>{mode === 'influence' ? 'Offer an influence' : 'Contribute a memory'}</h2>
      <p class="muted">
        {mode === 'influence'
          ? 'Soft context, not a command. The character may ignore or reinterpret it.'
          : 'Added to the main character’s private memory with Studio provenance.'}
      </p>
      <form
        onSubmit={event => {
          event.preventDefault();
          const operation =
            mode === 'memory'
              ? api.memory(text)
              : api.influence({
                  category,
                  strength,
                  pressure: 'balanced',
                  text,
                  need: '',
                  need_delta: 0,
                });
          void operation
            .then(() => refresh())
            .then(() => {
              setText('');
              setMessage('Saved');
            })
            .catch(error => setMessage(errorMessage(error)));
        }}
      >
        {mode === 'influence' && (
          <div class="form-row">
            <select value={category} onChange={event => setCategory(event.currentTarget.value as typeof category)}>
              <option value="want">Want</option>
              <option value="need">Need</option>
              <option value="suggestion">Suggestion</option>
            </select>
            <select value={strength} onChange={event => setStrength(event.currentTarget.value as typeof strength)}>
              <option value="soft">Soft</option>
              {category !== 'suggestion' && <option value="core">Core</option>}
            </select>
          </div>
        )}
        <textarea value={text} onInput={event => setText(event.currentTarget.value)} required maxLength={4000} />
        <button type="submit">Save {mode}</button>
        <output>{message}</output>
      </form>
    </section>
  );
}

function Dashboard({
  api,
  data,
  refresh,
  release,
}: {
  api: StudioApi;
  data: Workspace;
  refresh: () => Promise<void>;
  release: () => Promise<void>;
}) {
  const { projection, map, routes, journal } = data;
  const van = projection.van;
  const [routeTitle, setRouteTitle] = useState('Next chapter');
  const [waypoints, setWaypoints] = useState('');
  const [reflection, setReflection] = useState('');
  return (
    <main class="studio-shell">
      <header class="masthead">
        <div>
          <p class="eyebrow">Influence claim · {projection.claim.owner_subject}</p>
          <h1>{projection.character_name} <span>&amp; {van?.name ?? 'the open road'}</span></h1>
        </div>
        <div class="status-stack">
          <span class="status autonomous">● Autonomous controller active</span>
          <span>World epoch {projection.world_epoch}</span>
          <button onClick={() => void release()}>Release influence claim</button>
        </div>
      </header>

      <section class="hero-grid">
        <article class="panel scene-card">
          <p class="eyebrow">Current scene</p>
          <h2>{projection.scene.room_name || 'Between scenes'}</h2>
          <p>{projection.scene.visible_characters.length ? `Visible: ${projection.scene.visible_characters.join(', ')}` : 'No one else is currently visible.'}</p>
        </article>
        <article class="panel van-card">
          <p class="eyebrow">Mobile home</p>
          <h2>{van?.name ?? 'No Studio van'}</h2>
          {van && (
            <>
              <div class="meter"><i style={{ width: `${Math.min(100, (van.fuel_liters / van.tank_liters) * 100)}%` }} /></div>
              <p>{van.fuel_liters.toFixed(1)} L · about {van.estimated_range_km.toFixed(0)} km · {van.reliability}</p>
              {van.broken_down && <strong class="warning">Roadside assistance needed</strong>}
            </>
          )}
        </article>
      </section>

      <section class="panel map-panel">
        <div class="section-heading"><div><p class="eyebrow">Travel montage</p><h2>The red line so far</h2></div><button onClick={() => void refresh()}>Replay / refresh</button></div>
        <JourneyMap journey={map} />
        {map.warnings.map(warning => (
          <p class="warning" key={warning}>{warning}</p>
        ))}
      </section>

      <section class="lower-grid">
        <Composer api={api} refresh={refresh} />
        <section class="panel">
          <p class="eyebrow">Itinerary</p>
          <h2>Shape the road ahead</h2>
          {routes.map(route => <p key={route.id}><strong>{route.title}</strong> · {route.status} · stop {route.current_waypoint + 1}/{route.waypoints.length}</p>)}
          <form onSubmit={event => { event.preventDefault(); void api.route(routeTitle, waypoints.split(',').map(value => value.trim()).filter(Boolean)).then(refresh); }}>
            <input value={routeTitle} onInput={event => setRouteTitle(event.currentTarget.value)} aria-label="Route title" />
            <input value={waypoints} onInput={event => setWaypoints(event.currentTarget.value)} placeholder="location ids, comma separated" aria-label="Waypoints" />
            <button type="submit">Save itinerary</button>
          </form>
        </section>
      </section>

      <section class="panel journal">
        <p class="eyebrow">Travel journal</p>
        <h2>Moments worth keeping</h2>
        <form
          class="reflection-form"
          onSubmit={event => {
            event.preventDefault();
            void api
              .reflection(reflection)
              .then(refresh)
              .then(() => setReflection(''));
          }}
        >
          <input
            value={reflection}
            onInput={event => setReflection(event.currentTarget.value)}
            placeholder="Add a first-person travel reflection"
            required
          />
          <button type="submit">Write reflection</button>
        </form>
        <div class="journal-grid">
          {journal.map(moment => (
            <article key={moment.id} class={moment.pinned ? 'moment pinned' : 'moment'}>
              <small>{moment.kind} · epoch {moment.occurred_at_epoch}</small>
              <p>{moment.first_person ? <em>{moment.summary}</em> : moment.summary}</p>
              <div class="moment-actions">
                <button onClick={() => void api.pin(moment.id).then(refresh)}>Pin</button>
                {projection.media_available.image && <button onClick={() => void api.media(moment.id, 'image').then(refresh)}>Image</button>}
                {projection.media_available.video && <button onClick={() => void api.media(moment.id, 'video').then(refresh)}>Video</button>}
              </div>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}

export function App() {
  const api = useMemo(() => new StudioApi(), []);
  const [signedIn, setSignedIn] = useState<boolean | null>(null);
  const [choices, setChoices] = useState<CharacterChoice[]>([]);
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [error, setError] = useState('');
  const refresh = async () => {
    const [projection, map, routes, journal] = await Promise.all([
      api.projection(), api.map(), api.routes(), api.journal(),
    ]);
    setWorkspace({ projection, map, routes, journal });
  };
  const loadChoices = async () => setChoices(await api.characters());
  useEffect(() => {
    void api.session().then(() => setSignedIn(true)).catch(() => setSignedIn(false));
  }, [api]);
  useEffect(() => {
    if (!signedIn) return;
    void refresh().catch(() => loadChoices().catch(problem => setError(errorMessage(problem))));
  }, [api, signedIn]);
  useEffect(() => {
    if (!workspace) return;
    return api.observe(() => void refresh());
  }, [api, Boolean(workspace)]);
  if (signedIn === null) return <main class="welcome"><p>Opening Studio…</p></main>;
  if (!signedIn) return <SignIn onSignIn={(username, password) => api.login(username, password).then(() => setSignedIn(true))} />;
  if (error) return <main class="welcome"><h1>Studio could not open</h1><p>{error}</p><button onClick={() => void api.logout().finally(() => { setSignedIn(false); setError(''); })}>Use another account</button></main>;
  if (!workspace)
    return (
      <ClaimScreen
        api={api}
        choices={choices}
        onClaim={id => api.claim(id).then(refresh)}
        reload={loadChoices}
      />
    );
  return (
    <Dashboard
      api={api}
      data={workspace}
      refresh={refresh}
      release={() =>
        api.release().then(() => {
          setWorkspace(null);
          return loadChoices();
        })
      }
    />
  );
}
