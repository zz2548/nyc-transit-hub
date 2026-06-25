import { useEffect, useState } from "react";
import { api } from "../api/client";
import { canonicalRouteId } from "../lib/routeGeometry";
import type { StationArrivals, StopArrival } from "../types";
import { RouteBullet } from "./RouteBullet";

interface StationPanelProps {
  stopId: string;
  onClose: () => void;
}

function minuteLabel(minutes: number): string {
  if (minutes <= 0) return "Now";
  if (minutes === 1) return "1 min";
  return `${minutes} min`;
}

function ArrivalRow({ arrival }: { arrival: StopArrival }) {
  const rid = canonicalRouteId(arrival.route_id);
  const isNow = arrival.minutes_away <= 0;
  return (
    <li className="station-panel__arrival">
      <RouteBullet routeId={rid} size={22} />
      <span className="station-panel__arrival-dest">
        {arrival.headsign ?? "—"}
      </span>
      <span className={`station-panel__arrival-time${isNow ? " station-panel__arrival-time--now" : ""}`}>
        {minuteLabel(arrival.minutes_away)}
      </span>
    </li>
  );
}

export function StationPanel({ stopId, onClose }: StationPanelProps) {
  const [data, setData] = useState<StationArrivals | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    setData(null);
    api.stationArrivals(stopId)
      .then(setData)
      .catch(() => undefined)
      .finally(() => setLoading(false));
  }, [stopId]);

  // Group arrivals by route for a compact display
  const byRoute = data
    ? data.arrivals.reduce<Record<string, StopArrival[]>>((acc, a) => {
        const rid = canonicalRouteId(a.route_id);
        (acc[rid] ??= []).push(a);
        return acc;
      }, {})
    : {};

  return (
    <div className="station-panel">
      <div className="station-panel__header">
        <div>
          <p className="station-panel__eyebrow">Station</p>
          <h2 className="station-panel__name">{data?.name ?? "Loading…"}</h2>
        </div>
        <button className="route-panel__close" onClick={onClose} aria-label="Close">✕</button>
      </div>

      {loading && <p className="route-panel__loading">Loading arrivals…</p>}

      {data && !loading && (
        <>
          {data.arrivals.length === 0 ? (
            <p className="route-panel__loading">No upcoming arrivals in the next 90 min.</p>
          ) : (
            <div className="station-panel__section">
              <p className="station-panel__section-label">Upcoming arrivals</p>
              {Object.entries(byRoute).map(([rid, arrivals]) => (
                <div key={rid} className="station-panel__route-block">
                  <div className="station-panel__route-header">
                    <RouteBullet routeId={rid} size={18} />
                    <span className="station-panel__route-times">
                      {arrivals.slice(0, 5).map((a) => (
                        <span
                          key={a.trip_id}
                          className={`station-panel__chip${a.minutes_away <= 0 ? " station-panel__chip--now" : ""}`}
                        >
                          {minuteLabel(a.minutes_away)}
                        </span>
                      ))}
                    </span>
                  </div>
                  {arrivals[0]?.headsign && (
                    <p className="station-panel__headsign">
                      To {arrivals[0].headsign}
                    </p>
                  )}
                  <ul className="station-panel__arrivals">
                    {arrivals.slice(0, 6).map((a) => (
                      <ArrivalRow key={a.trip_id} arrival={a} />
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          )}

          {data.connections.length > 0 && (
            <div className="station-panel__section">
              <p className="station-panel__section-label">Nearby connections</p>
              <ul className="station-panel__connections">
                {data.connections.map((c) => (
                  <li key={c.stop_id} className="station-panel__connection">
                    <div className="station-panel__connection-routes">
                      {c.routes.map((r) => (
                        <RouteBullet key={r} routeId={canonicalRouteId(r)} size={20} />
                      ))}
                    </div>
                    <div className="station-panel__connection-info">
                      <span className="station-panel__connection-name">{c.name}</span>
                      <span className="station-panel__connection-dist">
                        {c.distance_m < 100 ? "< 100 m" : `${c.distance_m} m`} walk
                      </span>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
    </div>
  );
}
