import L from "leaflet";
import { useMemo } from "react";
import { CircleMarker, MapContainer, Marker, Popup, TileLayer } from "react-leaflet";
import { routeColorVar, routeTextColor } from "../lib/routeColors";
import type { ServiceAlert, Station, VehicleSnapshot } from "../types";
import { RouteBullet } from "./RouteBullet";

const NYC_CENTER: [number, number] = [40.7128, -73.94];

interface TransitMapProps {
  stations: Station[];
  vehicles: VehicleSnapshot[];
  alerts: ServiceAlert[];
}

/** Multiple trains can be "at" the same station simultaneously (different
 * lines, or local/express on the same line). Spread them around the
 * station's point so they're each clickable instead of stacking exactly
 * on top of one another. Deterministic so markers don't jitter on re-render.
 */
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

function vehicleIcon(routeId: string, hasDelay: boolean): L.DivIcon {
  const bg = routeColorVar(routeId);
  const fg = routeTextColor(routeId);
  return L.divIcon({
    className: "vehicle-marker",
    html: `<span class="vehicle-marker__bullet${hasDelay ? " vehicle-marker__bullet--delayed" : ""}" style="background:${bg};color:${fg}">${routeId}</span>`,
    iconSize: [20, 20],
    iconAnchor: [10, 10],
  });
}

export function TransitMap({ stations, vehicles, alerts }: TransitMapProps) {
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

      {[...vehiclesByStop.entries()].flatMap(([, group]) =>
        group.map((vehicle, index) => {
          const station = stations.find((s) => s.stop_id === vehicle.stop_id);
          if (!station) return null;
          const [dx, dy] = offsetFor(vehicle.trip_id, index, group.length);

          return (
            <Marker
              key={vehicle.trip_id}
              position={[station.lat + dy, station.lon + dx]}
              icon={vehicleIcon(vehicle.route_id, vehicle.has_delay_alert)}
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
    </MapContainer>
  );
}
