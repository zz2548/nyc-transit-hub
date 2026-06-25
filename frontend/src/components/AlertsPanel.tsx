import { relativeTime } from "../lib/time";
import type { ServiceAlert } from "../types";
import { RouteBullet } from "./RouteBullet";

interface AlertsPanelProps {
  alerts: ServiceAlert[];
}

export function AlertsPanel({ alerts }: AlertsPanelProps) {
  return (
    <section className="panel alerts-panel" aria-label="Active service alerts">
      <h2 className="panel__eyebrow">SERVICE ALERTS — {alerts.length} ACTIVE</h2>

      {alerts.length === 0 ? (
        <p className="alerts-panel__empty">No active alerts. Service is running normally.</p>
      ) : (
        <ol className="alerts-panel__list">
          {alerts.map((alert) => (
            <li key={alert.id} className="alerts-panel__row">
              <span className="alerts-panel__routes">
                {alert.routes.map((route) => (
                  <RouteBullet key={route} routeId={route} size={18} />
                ))}
              </span>
              <span className="alerts-panel__text">{alert.header_text}</span>
              <span className="alerts-panel__time">{relativeTime(alert.starts_at) ?? "—"}</span>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
