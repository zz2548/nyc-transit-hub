import L from "leaflet";
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
import { routeColorVar, routeTextColor } from "../lib/routeColors";
import { bearingAtStation, offsetPolyline, routeOffsetMeters, shapePointsForVehicle } from "../lib/routeGeometry";
import type { RouteSegment, RouteShape, ServiceAlert, Station, VehicleSnapshot } from "../types";
import { RouteBullet } from "./RouteBullet";

const NYC_CENTER: [number, number] = [40.7128, -73.94];

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

/**
 * Build a vehicle marker icon.
 * `bearing` is the geographic heading in degrees (0=north, clockwise).
 * The arrow tip always points in the direction of travel; the circle stays
 * at the anchor point regardless of rotation.
 */
function vehicleIcon(routeId: string, bearing: number | null, hasDelay: boolean): L.DivIcon {
  const bg = routeColorVar(routeId);
  const fg = routeTextColor(routeId);
  const r = 11;       // circle radius px
  const arrowH = 9;   // protrusion length px
  const arrowW = 7;   // arrow base half-width px
  // Canvas must contain circle + arrow in any direction → side = (r + arrowH) * 2
  const side = (r + arrowH) * 2;
  const c = side / 2; // centre of canvas = centre of circle

  const delayRing = hasDelay
    ? `<circle cx="0" cy="0" r="${r + 3}" fill="none" stroke="var(--live)" stroke-width="2"/>`
    : "";

  // Arrow points toward negative-y (up) in the SVG's local frame; rotation
  // is applied as CSS on the svg element so the circle stays on the anchor.
  const arrowPoly = bearing !== null
    ? `<polygon points="0,${-(r + arrowH)} ${-arrowW},${-r + 3} ${arrowW},${-r + 3}" fill="${bg}"/>`
    : "";

  const rotateCss = bearing !== null ? `transform:rotate(${bearing}deg);transform-origin:50% 50%` : "";

  const svg = `<svg width="${side}" height="${side}" viewBox="${-c} ${-c} ${side} ${side}"
    xmlns="http://www.w3.org/2000/svg" style="${rotateCss}">
    ${arrowPoly}
    ${delayRing}
    <circle cx="0" cy="0" r="${r}" fill="${bg}"/>
    <text x="0" y="4" text-anchor="middle"
      font-family="Helvetica Neue,Arial,sans-serif" font-weight="700" font-size="11"
      fill="${fg}">${routeId}</text>
  </svg>`;

  return L.divIcon({
    className: "vehicle-marker",
    html: svg,
    iconSize: [side, side],
    iconAnchor: [c, c], // always the circle centre
  });
}

export function TransitMap({ stations, vehicles, alerts, segments, shapes, onRouteClick }: TransitMapProps) {
  const vehiclesByStop = useMemo(() => {
    const map = new Map<string, VehicleSnapshot[]>();
    for (const vehicle of vehicles) {
      if (!vehicle.stop_id) continue;
      const list = map.get(vehicle.stop_id) ?? [];
      list.push(vehicle);
      map.set(vehicle.stop_id, list);
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

  // Resolved shapes — prefer GTFS shapes, fall back to straight segments
  const resolvedShapes = useMemo(() => {
    if (shapes.length > 0) return shapes;
    return segments.map((s) => ({
      route_id: s.route_id,
      shape_id: `${s.route_id}-${s.a.stop_id}-${s.b.stop_id}`,
      points: [[s.a.lat, s.a.lon], [s.b.lat, s.b.lon]] as [number, number][],
    }));
  }, [shapes, segments]);

  // Per-vehicle geographic bearing derived from the GTFS shape at the vehicle's station
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

  const renderedLines = useMemo(() =>
    resolvedShapes.map((shape) => {
      const pts = offsetPolyline(shape.points, routeOffsetMeters(shape.route_id));
      return { shape, pts };
    }),
  [resolvedShapes]);

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
            {renderedLines.map(({ shape, pts }) => (
              <Polyline
                key={shape.shape_id}
                positions={pts}
                pathOptions={{
                  color: routeColorVar(shape.route_id),
                  weight: 3.5,
                  opacity: 0.9,
                  lineCap: "round",
                  lineJoin: "round",
                }}
                eventHandlers={{ click: () => onRouteClick(shape.route_id) }}
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

              return (
                <CircleMarker
                  key={station.stop_id}
                  center={[station.lat, station.lon]}
                  radius={3}
                  pathOptions={{ color: "#bdbcb6", fillColor: "#bdbcb6", fillOpacity: 0.85, weight: 0 }}
                >
                  <Popup>
                    <div className="station-popup">
                      <strong>{station.name}</strong>
                      {here.length > 0 ? (
                        <ul>
                          {here.map((v) => (
                            <li key={v.trip_id}>
                              <RouteBullet routeId={v.route_id} size={16} /> {v.location_status?.replace(/_/g, " ").toLowerCase()}
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
                    icon={vehicleIcon(vehicle.route_id, vehicleBearings.get(vehicle.trip_id) ?? null, vehicle.has_delay_alert)}
                  >
                    <Popup>
                      <div className="station-popup">
                        <strong>
                          {vehicle.route_id} train {vehicle.direction === "N" ? "northbound" : "southbound"}
                        </strong>
                        <p>To {vehicle.headsign ?? "unknown terminal"}</p>
                        <p>
                          {vehicle.location_status?.replace(/_/g, " ").toLowerCase()} {station.name}
                        </p>
                        {vehicle.has_delay_alert && <p className="station-popup__alert">⚠ Delay reported</p>}
                      </div>
                    </Popup>
                  </Marker>
                );
              }),
            )}
          </LayerGroup>
        </LayersControl.Overlay>
      </LayersControl>
    </MapContainer>
  );
}
