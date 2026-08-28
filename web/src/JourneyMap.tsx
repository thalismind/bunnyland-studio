import { useEffect, useRef } from 'preact/hooks';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

import type { MapLocation, MapResource, MapSegment } from './types';

const segmentClass = (segment: MapSegment): string =>
  segment.state === 'completed'
    ? 'route-completed'
    : segment.state === 'detour'
      ? 'route-detour'
      : 'route-future';

const lookup = (map: MapResource, id: string): MapLocation | undefined =>
  map.locations.find(location => location.id === id);

function RealMap({ journey }: { journey: MapResource }) {
  const target = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!target.current) return;
    const first = journey.locations[0];
    const map = L.map(target.current, { zoomControl: true }).setView(
      first ? [first.point.latitude, first.point.longitude] : [0, 0],
      first ? 7 : 2,
    );
    L.tileLayer(journey.tile_url, { attribution: journey.attribution, maxZoom: 19 }).addTo(map);
    for (const segment of journey.segments) {
      const start = lookup(journey, segment.from_location_id);
      const end = lookup(journey, segment.to_location_id);
      if (!start || !end) continue;
      L.polyline(
        [
          [start.point.latitude, start.point.longitude],
          [end.point.latitude, end.point.longitude],
        ],
        {
          color: segment.state === 'detour' ? '#d78c2b' : '#a62020',
          opacity: segment.state === 'future' ? 0.35 : 0.95,
          weight: segment.state === 'completed' ? 6 : 3,
          dashArray: segment.state === 'detour' ? '10 8' : undefined,
        },
      ).addTo(map);
    }
    for (const place of journey.locations) {
      L.circleMarker([place.point.latitude, place.point.longitude], {
        radius: place.id === journey.current_location_id ? 9 : 5,
        color: place.id === journey.current_location_id ? '#fff4d2' : '#722020',
        fillColor: '#a62020',
        fillOpacity: 1,
      })
        .bindTooltip(`${place.name} · ${place.kind}`)
        .addTo(map);
    }
    return () => map.remove();
  }, [journey]);
  return <div class="leaflet-map" ref={target} aria-label="Real journey map" />;
}

function FictionalMap({ journey }: { journey: MapResource }) {
  if (!journey.locations.length) return <p>No geography has been generated yet.</p>;
  const latitudes = journey.locations.map(place => place.point.latitude);
  const longitudes = journey.locations.map(place => place.point.longitude);
  const minLat = Math.min(...latitudes);
  const maxLat = Math.max(...latitudes);
  const minLon = Math.min(...longitudes);
  const maxLon = Math.max(...longitudes);
  const x = (longitude: number) => 45 + ((longitude - minLon) / (maxLon - minLon || 1)) * 810;
  const y = (latitude: number) => 455 - ((latitude - minLat) / (maxLat - minLat || 1)) * 390;
  return (
    <svg class="fictional-map" viewBox="0 0 900 500" role="img" aria-label="Fictional journey map">
      <defs>
        <filter id="paper">
          <feTurbulence type="fractalNoise" baseFrequency=".04" numOctaves="3" result="noise" />
          <feBlend in="SourceGraphic" in2="noise" mode="multiply" />
        </filter>
      </defs>
      <rect width="900" height="500" class="map-paper" />
      {journey.segments.map(segment => {
        const start = lookup(journey, segment.from_location_id);
        const end = lookup(journey, segment.to_location_id);
        return start && end ? (
          <line
            key={segment.id}
            class={segmentClass(segment)}
            x1={x(start.point.longitude)}
            y1={y(start.point.latitude)}
            x2={x(end.point.longitude)}
            y2={y(end.point.latitude)}
          />
        ) : null;
      })}
      {journey.locations.map(place => (
        <g key={place.id} transform={`translate(${x(place.point.longitude)} ${y(place.point.latitude)})`}>
          <circle class={place.id === journey.current_location_id ? 'van-marker' : 'place-marker'} r="7" />
          <text x="11" y="-9">{place.name}</text>
          <text class="place-kind" x="11" y="8">{place.kind}</text>
        </g>
      ))}
    </svg>
  );
}

export function JourneyMap({ journey }: { journey: MapResource }) {
  return (
    <figure class="journey-map">
      {journey.mode === 'real' ? <RealMap journey={journey} /> : <FictionalMap journey={journey} />}
      <figcaption>{journey.attribution}</figcaption>
    </figure>
  );
}
