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
import { offsetPolyline, routeOffsetMeters } from "../lib/routeGeometry";
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

function vehicleIcon(routeId: string, direction: "N" | "S" | null, hasDelay: boolean): L.DivIcon {
  const bg = routeColorVar(routeId);
  const fg = routeTextColor(routeId);
  // Arrow points up for N, down for S; omitted when direction unknown
  const arrow =
    direction === "N"
      ? `<svg width="10" height="10" viewBox="0 0 10 10" style="display:block;margin:0 auto"><polygon points="5,1 9,9 5,7 1,9" fill="${fg}"/></svg>`
      : direction === "S"
        ? `<svg width="10" height="10" viewBox="0 0 10 10" style="display:block;margin:0 auto;transform:rotate(180deg)"><polygon points="5,1 9,9 5,7 1,9" fill="${fg}"/></svg>`
        : "";
  return L.divIcon({
    className: "vehicle-marker",
    html: `<div class="vehicle-marker__inner${hasDelay ? " vehicle-marker__inner--delayed" : ""}" style="background:${bg};color:${fg}">
      ${arrow}
      <span class="vehicle-marker__label">${routeId}</span>
    </div>`,
    iconSize: [22, direction ? 32 : 22],
    iconAnchor: [11, direction ? 16 : 11],
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
                    icon={vehicleIcon(vehicle.route_id, vehicle.direction, vehicle.has_delay_alert)}
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
