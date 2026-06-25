import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import { routeColorVar, routeTextColor } from "../lib/routeColors";
import type { RouteDirection, RouteStopEntry, RouteStops } from "../types";
import { RouteBullet } from "./RouteBullet";

interface RoutePanelProps {
  routeId: string;
  onClose: () => void;
}

function TrainDot({ status }: { status: string | null }) {
  const label =
    status === "STOPPED_AT" ? "●" : status === "INCOMING_AT" ? "→" : "◎";
  return <span className="route-panel__train-dot">{label}</span>;
}

function StopRow({ stop, isLast }: { stop: RouteStopEntry; isLast: boolean }) {
  const hasTrains = stop.vehicles.length > 0;
  return (
    <li className={`route-panel__stop${hasTrains ? " route-panel__stop--active" : ""}`}>
      <span className="route-panel__stop-line">
        <span className="route-panel__stop-track" />
        <span className={`route-panel__stop-dot${isLast ? " route-panel__stop-dot--terminal" : ""}`} />
      </span>
      <span className="route-panel__stop-name">{stop.name}</span>
      {hasTrains && (
        <span className="route-panel__trains">
          {stop.vehicles.map((v) => (
            <TrainDot key={v.trip_id} status={v.location_status} />
          ))}
        </span>
      )}
    </li>
  );
}

function DirectionPane({ dir, color }: { dir: RouteDirection; color: string }) {
  return (
    <div className="route-panel__direction">
      <p className="route-panel__headsign">To {dir.headsign}</p>
      <ul className="route-panel__stops">
        {dir.stops.map((stop, i) => (
          <StopRow key={stop.stop_id} stop={stop} isLast={i === dir.stops.length - 1} />
        ))}
      </ul>
    </div>
  );
}

export function RoutePanel({ routeId, onClose }: RoutePanelProps) {
  const [data, setData] = useState<RouteStops | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeDir, setActiveDir] = useState(0);
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setLoading(true);
    setData(null);
    setActiveDir(0);
    api.routeStops(routeId).then((d) => {
      setData(d);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [routeId]);

  const color = routeColorVar(routeId);
  const textColor = routeTextColor(routeId);

  return (
    <div className="route-panel" ref={panelRef}>
      <div className="route-panel__header" style={{ background: color, color: textColor }}>
        <RouteBullet routeId={routeId} size={28} />
        <span className="route-panel__title">Line</span>
        <button className="route-panel__close" onClick={onClose} aria-label="Close">✕</button>
      </div>

      {loading && <p className="route-panel__loading">Loading stops…</p>}

      {data && (
        <>
          {data.directions.length > 1 && (
            <div className="route-panel__dir-tabs">
              {data.directions.map((dir, i) => (
                <button
                  key={dir.direction_id}
                  className={`route-panel__dir-tab${i === activeDir ? " route-panel__dir-tab--active" : ""}`}
                  onClick={() => setActiveDir(i)}
                  style={i === activeDir ? { borderBottomColor: color } : undefined}
                >
                  {dir.headsign}
                </button>
              ))}
            </div>
          )}
          <DirectionPane dir={data.directions[activeDir]} color={color} />
        </>
      )}
    </div>
  );
}
