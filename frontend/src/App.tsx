import { useEffect, useState } from "react";
import { api } from "./api/client";
import { AlertsPanel } from "./components/AlertsPanel";
import { DelayChart } from "./components/DelayChart";
import { Header } from "./components/Header";
import { TransitMap } from "./components/TransitMap";
import { relativeTime } from "./lib/time";
import type { AlertsByRoute, ServiceAlert, Station, VehicleSnapshot } from "./types";
import "./App.css";

const POLL_INTERVAL_MS = 30_000;

export default function App() {
  const [stations, setStations] = useState<Station[]>([]);
  const [vehicles, setVehicles] = useState<VehicleSnapshot[]>([]);
  const [alerts, setAlerts] = useState<ServiceAlert[]>([]);
  const [alertsByRoute, setAlertsByRoute] = useState<AlertsByRoute[]>([]);
  const [lastSyncIso, setLastSyncIso] = useState<string | null>(null);
  const [isLive, setIsLive] = useState(false);

  // Stations are static reference data -- fetch once.
  useEffect(() => {
    api.stations().then(setStations).catch(() => undefined);
  }, []);

  // Everything else is "right now" -- poll on an interval rather than
  // opening a socket, since the backend itself only refreshes every 30s.
  useEffect(() => {
    let cancelled = false;

    const poll = async () => {
      try {
        const [nextVehicles, nextAlerts, nextAlertsByRoute] = await Promise.all([
          api.vehicles(),
          api.alerts(),
          api.alertsByRoute(),
        ]);
        if (cancelled) return;
        setVehicles(nextVehicles);
        setAlerts(nextAlerts);
        setAlertsByRoute(nextAlertsByRoute);
        setLastSyncIso(new Date().toISOString());
        setIsLive(true);
      } catch {
        if (!cancelled) setIsLive(false);
      }
    };

    poll();
    const interval = setInterval(poll, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  return (
    <div className="app-shell">
      <Header isLive={isLive} lastSync={relativeTime(lastSyncIso)} vehicleCount={vehicles.length} />

      <main className="app-main">
        <TransitMap stations={stations} vehicles={vehicles} alerts={alerts} />

        <aside className="app-sidebar">
          <AlertsPanel alerts={alerts} />
          <DelayChart data={alertsByRoute} />
        </aside>
      </main>
    </div>
  );
}
