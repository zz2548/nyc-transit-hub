import L from "leaflet";
import "leaflet-polylineoffset";
import { useMemo } from "react";
import {
  CircleMarker,
  LayerGroup,
  LayersControl,
  MapContainer,
  Marker,
  Polyline,
  Popup,
  TileLayer,
} from "react-leaflet";
import { routeColorHex, routeColorVar, routeTextColor } from "../lib/routeColors";
import { bearingAtStation, canonicalRouteId, routeOffsetSlot, shapePointsForVehicle } from "../lib/routeGeometry";
import type { RouteSegment, RouteShape, ServiceAlert, Station, VehicleSnapshot } from "../types";
import { RouteBullet } from "./RouteBullet";

const NYC_CENTER: [number, number] = [40.7128, -73.94];
const LINE_WEIGHT = 3;

const OffsetPolyline = Polyline as React.ComponentType<
  React.ComponentProps<typeof Polyline> & { offset?: number }
>;

// Routes whose segments define express stops
const EXPRESS_ROUTE_IDS = new Set(["2", "3", "4", "5", "A", "B", "D", "N", "Q", "J", "Z"]);

const LEGEND_GROUPS = [
  { label: "1 · 2 · 3",      color: "#ee352e" },
  { label: "4 · 5 · 6",      color: "#00933c" },
  { label: "7",               color: "#b933ad" },
  { label: "A · C · E",      color: "#0039a6" },
  { label: "B · D · F · M",  color: "#ff6319" },
  { label: "G",               color: "#6cbe45" },
  { label: "J · Z",          color: "#996633" },
  { label: "L",               color: "#a7a9ac" },
  { label: "N · Q · R · W",  color: "#fccc0a" },
  { label: "SIR",             color: "#0078c6" },
  { label: "S (shuttle)",     color: "#808183" },
];

function MapLegend() {
  return (
    <div className="map-legend">
      <p className="map-legend__heading">Lines</p>
      {LEGEND_GROUPS.map(({ label, color }) => (
        <div key={label} className="map-legend__row">
          <span className="map-legend__swatch" style={{ background: color }} />
          <span className="map-legend__label">{label}</span>
        </div>
      ))}
      <p className="map-legend__heading" style={{ marginTop: 8 }}>Stops</p>
      <div className="map-legend__row">
        <span className="map-legend__dot map-legend__dot--express" />
        <span className="map-legend__label">Express</span>
      </div>
      <div className="map-legend__row">
        <span className="map-legend__dot map-legend__dot--local" />
        <span className="map-legend__label">Local</span>
      </div>
    </div>
  );
}

interface TransitMapProps {
  stations: Station[];
  vehicles: VehicleSnapshot[];
  alerts: ServiceAlert[];
  segments: RouteSegment[];
  shapes: RouteShape[];
  onRouteClick: (routeId: string) => void;
}

function offsetFor(tripId: string, index: number, total: number): [number, number] {
  if (total <= 1) return [0, 0];
  const angle = (2 * Math.PI * index) / total + hashToUnit(tripId);
  const radius = 0.00045;
  return [Math.cos(angle) * radius, Math.sin(angle) * radius];
}

function hashToUnit(value: string): number {
  let hash = 0;
  for (let i = 0; i < value.length; i++) hash = (hash * 31 + value.charCodeAt(i)) % 1000;
  return (hash / 1000) * Math.PI;
}

function vehicleIcon(routeId: string, bearing: number | null, hasDelay: boolean): L.DivIcon {
  const bg = routeColorVar(routeId);
  const fg = routeTextColor(routeId);
  const r = 11;
  const arrowH = 9;
  const arrowW = 7;
  const side = (r + arrowH) * 2;
  const c = side / 2;

  const delayRing = hasDelay
    ? `<circle cx="0" cy="0" r="${r + 3}" fill="none" stroke="var(--live)" stroke-width="2"/>`
    : "";
  const arrowPoly = bearing !== null
    ? `<polygon points="0,${-(r + arrowH)} ${-arrowW},${-r + 3} ${arrowW},${-r + 3}" fill="${bg}"/>`
    : "";
  const rotateCss = bearing !== null ? `transform:rotate(${bearing}deg);transform-origin:50% 50%` : "";

  const svg = `<svg width="${side}" height="${side}" viewBox="${-c} ${-c} ${side} ${side}"
    xmlns="http://www.w3.org/2000/svg" style="${rotateCss}">
    ${arrowPoly}${delayRing}
    <circle cx="0" cy="0" r="${r}" fill="${bg}"/>
    <text x="0" y="4" text-anchor="middle"
      font-family="Helvetica Neue,Arial,sans-serif" font-weight="700" font-size="11"
      fill="${fg}">${routeId}</text>
  </svg>`;

  return L.divIcon({
    className: "vehicle-marker",
    html: svg,
    iconSize: [side, side],
    iconAnchor: [c, c],
  });
}

export function TransitMap({ stations, vehicles, alerts, segments, shapes, onRouteClick }: TransitMapProps) {
  const vehiclesByStop = useMemo(() => {
    const map = new Map<string, VehicleSnapshot[]>();
    for (const v of vehicles) {
      if (!v.stop_id) continue;
      const list = map.get(v.stop_id) ?? [];
      list.push(v);
      map.set(v.stop_id, list);
    }
    return map;
  }, [vehicles]);

  const alertsByRoute = useMemo(() => {
    const map = new Map<string, ServiceAlert[]>();
    for (const alert of alerts) {
      for (const route of alert.routes) {
        const list = map.get(route) ?? [];
        list.push(alert);
        map.set(route, list);
      }
    }
    return map;
  }, [alerts]);

  // One polyline per canonical route: merge API variants (6X→6, 7X→7, FX→F,
  // GS/FS/H→S) and pick the longest shape across all variants.
  const dedupedShapes = useMemo(() => {
    const source = shapes.length > 0 ? shapes : segments.map((s) => ({
      route_id: s.route_id,
      shape_id: `${s.route_id}-${s.a.stop_id}-${s.b.stop_id}`,
      points: [[s.a.lat, s.a.lon], [s.b.lat, s.b.lon]] as [number, number][],
    }));
    const byRoute = new Map<string, { canonical_id: string; shape_id: string; points: [number, number][] }>();
    for (const shape of source) {
      const cid = canonicalRouteId(shape.route_id);
      const existing = byRoute.get(cid);
      if (!existing || shape.points.length > existing.points.length) {
        byRoute.set(cid, { canonical_id: cid, shape_id: shape.shape_id, points: shape.points });
      }
    }
    return [...byRoute.values()];
  }, [shapes, segments]);

  // Stations served by any express route → express dot; others → local ring
  const expressStops = useMemo(() => {
    const set = new Set<string>();
    for (const seg of segments) {
      if (EXPRESS_ROUTE_IDS.has(seg.route_id.toUpperCase())) {
        set.add(seg.a.stop_id);
        set.add(seg.b.stop_id);
      }
    }
    return set;
  }, [segments]);

  const vehicleBearings = useMemo(() => {
    const map = new Map<string, number>();
    for (const v of vehicles) {
      if (!v.stop_id || !v.direction) continue;
      const station = stations.find((s) => s.stop_id === v.stop_id);
      if (!station) continue;
      const pts = shapePointsForVehicle(v.route_id, v.direction, shapes);
      if (!pts) continue;
      map.set(v.trip_id, bearingAtStation(station.lat, station.lon, pts));
    }
    return map;
  }, [vehicles, stations, shapes]);

  return (
    <MapContainer
      center={NYC_CENTER}
      zoom={12}
      minZoom={10}
      maxZoom={17}
      className="transit-map"
      attributionControl={false}
    >
      <TileLayer
        url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        subdomains="abcd"
        attribution="&copy; OpenStreetMap contributors &copy; CARTO"
      />

      <LayersControl position="topright">
        <LayersControl.Overlay name="Lines" checked>
          <LayerGroup>
            {dedupedShapes.map((shape) => (
              <OffsetPolyline
                key={shape.shape_id}
                positions={shape.points}
                offset={routeOffsetSlot(shape.canonical_id) * LINE_WEIGHT}
                pathOptions={{
                  color: routeColorHex(shape.canonical_id),
                  weight: LINE_WEIGHT,
                  opacity: 0.9,
                  lineCap: "round",
                  lineJoin: "round",
                }}
                eventHandlers={{ click: () => onRouteClick(shape.canonical_id) }}
              />
            ))}
          </LayerGroup>
        </LayersControl.Overlay>

        <LayersControl.Overlay name="Stations" checked>
          <LayerGroup>
            {stations.map((station) => {
              const here = vehiclesByStop.get(station.stop_id) ?? [];
              const routesHere = new Set(here.map((v) => v.route_id));
              const stationAlerts = [...routesHere].flatMap((r) => alertsByRoute.get(r) ?? []);
              const isExpress = expressStops.has(station.stop_id);

              return (
                <CircleMarker
                  key={station.stop_id}
                  center={[station.lat, station.lon]}
                  radius={isExpress ? 4 : 3}
                  pathOptions={
                    isExpress
                      ? { color: "#c8c7c1", fillColor: "#c8c7c1", fillOpacity: 1, weight: 0 }
                      : { color: "#c8c7c1", fillColor: "transparent", fillOpacity: 0, weight: 1.5 }
                  }
                >
                  <Popup>
                    <div className="station-popup">
                      <strong>{station.name}</strong>
                      {here.length > 0 ? (
                        <ul>
                          {here.map((v) => (
                            <li key={v.trip_id}>
                              <RouteBullet routeId={canonicalRouteId(v.route_id)} size={16} />{" "}
                              {v.location_status?.replace(/_/g, " ").toLowerCase()}
                              {v.direction ? ` · ${v.direction === "N" ? "northbound" : "southbound"}` : ""}
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p className="station-popup__empty">No trains currently here</p>
                      )}
                      {stationAlerts.length > 0 && (
                        <p className="station-popup__alert">⚠ {stationAlerts[0].header_text}</p>
                      )}
                    </div>
                  </Popup>
                </CircleMarker>
              );
            })}
          </LayerGroup>
        </LayersControl.Overlay>

        <LayersControl.Overlay name="Trains" checked>
          <LayerGroup>
            {[...vehiclesByStop.entries()].flatMap(([, group]) =>
              group.map((vehicle, index) => {
                const station = stations.find((s) => s.stop_id === vehicle.stop_id);
                if (!station) return null;
                const [dx, dy] = offsetFor(vehicle.trip_id, index, group.length);
                return (
                  <Marker
                    key={vehicle.trip_id}
                    position={[station.lat + dy, station.lon + dx]}
                    icon={vehicleIcon(
                      canonicalRouteId(vehicle.route_id),
                      vehicleBearings.get(vehicle.trip_id) ?? null,
                      vehicle.has_delay_alert,
                    )}
                  >
                    <Popup>
                      <div className="station-popup">
                        <strong>
                          {canonicalRouteId(vehicle.route_id)} train{" "}
                          {vehicle.direction === "N" ? "northbound" : "southbound"}
                        </strong>
                        <p>To {vehicle.headsign ?? "unknown terminal"}</p>
                        <p>
                          {vehicle.location_status?.replace(/_/g, " ").toLowerCase()}{" "}
                          {station.name}
                        </p>
                        {vehicle.has_delay_alert && (
                          <p className="station-popup__alert">⚠ Delay reported</p>
                        )}
                      </div>
                    </Popup>
                  </Marker>
                );
              }),
            )}
          </LayerGroup>
        </LayersControl.Overlay>
      </LayersControl>

      <MapLegend />
    </MapContainer>
  );
}
