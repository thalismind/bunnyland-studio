import {
  isCharacterChoices,
  isAuthSession,
  isInfluence,
  isJournal,
  isMapResource,
  isProjection,
  isRoutes,
  type CharacterChoice,
  type AuthSession,
  type InfluenceResource,
  type JournalResource,
  type MapResource,
  type ProjectionResource,
  type RouteResource,
} from './types';

const PLAY = '/api/v1/play/extensions/bunnyland.studio';
const ADMIN = '/api/v1/admin/extensions/bunnyland.studio';
const CLIENT_ID = 'bunnyland-studio-web';

export type Validator<T> = (value: unknown) => value is T;

export class StudioApi {
  private async request<T>(path: string, validate: Validator<T>, init?: RequestInit): Promise<T> {
    const response = await fetch(path, {
      ...init,
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        'X-Bunnyland-Client-Id': CLIENT_ID,
        ...init?.headers,
      },
    });
    if (!response.ok) {
      const message = await response.text();
      throw new Error(message || `${response.status} ${response.statusText}`);
    }
    const value = JSON.parse(await response.text()) as unknown;
    if (!validate(value)) throw new Error(`Invalid Studio response from ${path}`);
    return value;
  }

  login(username: string, password: string): Promise<AuthSession> {
    return this.request('/api/v1/auth/session', isAuthSession, {
      method: 'POST',
      body: JSON.stringify({ username, password, delivery: 'cookie' }),
    });
  }

  session(): Promise<AuthSession> {
    return this.request('/api/v1/auth/session', isAuthSession);
  }

  logout(): Promise<void> {
    return fetch('/api/v1/auth/session', {
      method: 'DELETE',
      credentials: 'same-origin',
      headers: { 'X-Bunnyland-Client-Id': CLIENT_ID },
    }).then(response => {
      if (!response.ok && response.status !== 401) {
        throw new Error(`${response.status} ${response.statusText}`);
      }
    });
  }

  characters(): Promise<CharacterChoice[]> {
    return this.request(`${PLAY}/characters`, isCharacterChoices);
  }

  claim(characterId: string): Promise<ProjectionResource> {
    return this.request(`${PLAY}/claims`, isRecordProjectionClaim, {
      method: 'POST',
      body: JSON.stringify({ character_id: characterId }),
    }).then(() => this.projection());
  }

  release(): Promise<void> {
    return this.request(`${PLAY}/claim`, isRecordValue, { method: 'DELETE' }).then(() => undefined);
  }

  projection(): Promise<ProjectionResource> {
    return this.request(`${PLAY}/projection`, isProjection);
  }

  map(): Promise<MapResource> {
    return this.request(`${PLAY}/map`, isMapResource);
  }

  routes(): Promise<RouteResource[]> {
    return this.request(`${PLAY}/routes`, isRoutes);
  }

  journal(): Promise<JournalResource[]> {
    return this.request(`${PLAY}/journal`, isJournal);
  }

  influence(body: {
    category: 'want' | 'need' | 'suggestion';
    strength: 'soft' | 'core';
    pressure: 'low' | 'balanced' | 'strong';
    text: string;
    need: string;
    need_delta: number;
  }): Promise<InfluenceResource> {
    return this.request(`${PLAY}/influences`, isInfluence, {
      method: 'POST',
      body: JSON.stringify(body),
    });
  }

  memory(text: string): Promise<void> {
    return this.request(`${PLAY}/memories`, isRecordValue, {
      method: 'POST',
      body: JSON.stringify({ text, tags: ['player-supplied'] }),
    }).then(() => undefined);
  }

  route(title: string, waypoints: string[]): Promise<void> {
    return this.request(`${PLAY}/routes`, isRecordValue, {
      method: 'POST',
      body: JSON.stringify({
        title,
        adherence: 'balanced',
        waypoints: waypoints.map(location_id => ({ location_id })),
      }),
    }).then(() => undefined);
  }

  reflection(text: string): Promise<void> {
    return this.request(`${PLAY}/journal/reflections`, isRecordValue, {
      method: 'POST',
      body: JSON.stringify({ text }),
    }).then(() => undefined);
  }

  pin(momentId: string): Promise<void> {
    return this.request(`${PLAY}/journal/${encodeURIComponent(momentId)}/pin`, isRecordValue, {
      method: 'PUT',
    }).then(() => undefined);
  }

  media(momentId: string, kind: 'image' | 'video'): Promise<void> {
    return this.request(`${PLAY}/journal/${encodeURIComponent(momentId)}/media`, isRecordValue, {
      method: 'POST',
      body: JSON.stringify({ kind, event_id: '' }),
    }).then(() => undefined);
  }

  generate(generator: 'studio-van-waifu-real' | 'studio-van-waifu-fictional', config: unknown) {
    return this.request('/api/v1/admin/world/generation-jobs', isRecordValue, {
      method: 'POST',
      body: JSON.stringify({
        kind: 'world',
        confirm_reset: true,
        generator,
        generator_config: config,
      }),
    });
  }

  resetClaim(characterId: string): Promise<void> {
    return this.request(`${ADMIN}/claims/${encodeURIComponent(characterId)}`, isRecordValue, {
      method: 'DELETE',
    }).then(() => undefined);
  }

  observe(onUpdate: () => void): () => void {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const socket = new WebSocket(`${protocol}//${location.host}${PLAY}/observer`);
    let lastSequence = -1;
    socket.addEventListener('open', () => {
      socket.send(
        JSON.stringify({ type: 'authenticate', data: { client_id: CLIENT_ID } }),
      );
    });
    socket.addEventListener('message', event => {
      if (typeof event.data !== 'string') return;
      const frame = JSON.parse(event.data) as unknown;
      if (!isRecordValue(frame)) return;
      const sequence = typeof frame.sequence === 'number' ? frame.sequence : lastSequence + 1;
      if (sequence <= lastSequence) return;
      lastSequence = sequence;
      onUpdate();
    });
    return () => socket.close(1000, 'Studio view closed');
  }
}

const isRecordValue = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value);
const isRecordProjectionClaim = isRecordValue;
