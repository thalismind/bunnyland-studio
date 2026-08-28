export type GeoPoint = { latitude: number; longitude: number };
export type AuthSession = {
  subject: string;
  scopes: string[];
  expires_at: number;
  rotate_after: number | null;
  rotation_eligible: boolean;
};

export type CharacterChoice = { id: string; name: string; claimed: boolean };
export type ClaimResource = {
  claim_id: string;
  character_id: string;
  owner_subject: string;
  claimed_at_epoch: number;
  last_activity_epoch: number;
  autonomous_controller_active: boolean;
};
export type InfluenceResource = {
  id: string;
  category: 'want' | 'need' | 'suggestion';
  strength: 'soft' | 'core';
  pressure: 'low' | 'balanced' | 'strong';
  text: string;
  need: string;
  need_delta: number;
};
export type VanResource = {
  name: string;
  description: string;
  fuel_liters: number;
  tank_liters: number;
  estimated_range_km: number;
  reliability: 'temperamental' | 'fair' | 'dependable';
  broken_down: boolean;
  current_location_id: string;
  autonomous_controller_active: boolean;
};
export type ProjectionResource = {
  world_epoch: number;
  character_id: string;
  character_name: string;
  claim: ClaimResource;
  van: VanResource | null;
  scene: { room_id: string; room_name: string; visible_characters: string[] };
  influences: InfluenceResource[];
  media_available: { image: boolean; video: boolean };
};
export type RouteResource = {
  id: string;
  title: string;
  adherence: 'loose' | 'balanced' | 'strict';
  status: 'planned' | 'active' | 'paused' | 'completed';
  current_waypoint: number;
  waypoints: string[];
};
export type JournalResource = {
  id: string;
  kind: string;
  summary: string;
  location_id: string;
  occurred_at_epoch: number;
  first_person: boolean;
  pinned: boolean;
  media_job_id: string;
  media_kind: '' | 'image' | 'video';
  media_source_event_id: string;
  media_status: '' | 'queued' | 'running' | 'succeeded' | 'failed' | 'expired';
  media_url: string;
  media_error: string;
};
export type MemoryResource = {
  id: string;
  text: string;
  tags: string[];
  source: string;
  created_at_epoch: number;
};
export type MapLocation = { id: string; name: string; kind: string; point: GeoPoint };
export type MapSegment = {
  id: string;
  from_location_id: string;
  to_location_id: string;
  state: 'future' | 'completed' | 'detour' | 'skipped';
  distance_km: number;
  occurred_at_epoch: number | null;
};
export type MapResource = {
  mode: 'real' | 'fictional';
  attribution: string;
  tile_url: string;
  current_location_id: string;
  locations: MapLocation[];
  segments: MapSegment[];
  warnings: string[];
};

export const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value);

export const isAuthSession = (value: unknown): value is AuthSession =>
  isRecord(value) &&
  typeof value.subject === 'string' &&
  Array.isArray(value.scopes) &&
  value.scopes.every(scope => typeof scope === 'string') &&
  typeof value.expires_at === 'number' &&
  (value.rotate_after === null || typeof value.rotate_after === 'number') &&
  typeof value.rotation_eligible === 'boolean';

export const isProjection = (value: unknown): value is ProjectionResource =>
  isRecord(value) &&
  typeof value.character_id === 'string' &&
  typeof value.character_name === 'string' &&
  isRecord(value.claim) &&
  typeof value.claim.owner_subject === 'string' &&
  isRecord(value.scene) &&
  Array.isArray(value.influences);

export const isMapResource = (value: unknown): value is MapResource =>
  isRecord(value) &&
  (value.mode === 'real' || value.mode === 'fictional') &&
  typeof value.attribution === 'string' &&
  typeof value.current_location_id === 'string' &&
  Array.isArray(value.locations) &&
  Array.isArray(value.segments) &&
  Array.isArray(value.warnings) &&
  value.warnings.every(warning => typeof warning === 'string');

export const isCharacterChoices = (value: unknown): value is CharacterChoice[] =>
  Array.isArray(value) &&
  value.every(
    item =>
      isRecord(item) &&
      typeof item.id === 'string' &&
      typeof item.name === 'string' &&
      typeof item.claimed === 'boolean',
  );

export const isRoutes = (value: unknown): value is RouteResource[] =>
  Array.isArray(value) &&
  value.every(
    route =>
      isRecord(route) &&
      typeof route.id === 'string' &&
      typeof route.title === 'string' &&
      Array.isArray(route.waypoints),
  );
export const isJournal = (value: unknown): value is JournalResource[] =>
  Array.isArray(value) &&
  value.every(
    moment =>
      isRecord(moment) &&
      typeof moment.id === 'string' &&
      typeof moment.kind === 'string' &&
      typeof moment.summary === 'string' &&
      typeof moment.location_id === 'string' &&
      typeof moment.occurred_at_epoch === 'number' &&
      typeof moment.first_person === 'boolean' &&
      typeof moment.pinned === 'boolean' &&
      typeof moment.media_job_id === 'string' &&
      (moment.media_kind === '' || moment.media_kind === 'image' || moment.media_kind === 'video') &&
      typeof moment.media_source_event_id === 'string' &&
      (moment.media_status === '' ||
        moment.media_status === 'queued' ||
        moment.media_status === 'running' ||
        moment.media_status === 'succeeded' ||
        moment.media_status === 'failed' ||
        moment.media_status === 'expired') &&
      typeof moment.media_url === 'string' &&
      typeof moment.media_error === 'string',
  );
export const isMemories = (value: unknown): value is MemoryResource[] =>
  Array.isArray(value) &&
  value.every(
    memory =>
      isRecord(memory) &&
      typeof memory.id === 'string' &&
      typeof memory.text === 'string' &&
      Array.isArray(memory.tags) &&
      memory.tags.every(tag => typeof tag === 'string') &&
      typeof memory.source === 'string' &&
      typeof memory.created_at_epoch === 'number',
  );
export const isInfluence = (value: unknown): value is InfluenceResource =>
  isRecord(value) && typeof value.id === 'string' && typeof value.text === 'string';
