interface HeaderProps {
  isLive: boolean;
  lastSync: string | null;
  vehicleCount: number;
}

export function Header({ isLive, lastSync, vehicleCount }: HeaderProps) {
  return (
    <header className="app-header">
      <div className="app-header__brand">
        <span className="app-header__mark" aria-hidden="true" />
        <h1>NYC TRANSIT HUB</h1>
      </div>

      <div className="app-header__status">
        <span className="app-header__count">{vehicleCount} trains tracked</span>
        <span className={`live-indicator ${isLive ? "live-indicator--on" : ""}`}>
          <span className="live-indicator__dot" />
          {isLive ? "LIVE" : "CONNECTING"}
        </span>
        {lastSync && <span className="app-header__synced">synced {lastSync}</span>}
      </div>
    </header>
  );
}
