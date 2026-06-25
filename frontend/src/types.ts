export interface Station {
  stop_id: string;
  name: string;
  lat: number;
  lon: number;
}

export type LocationStatus = "INCOMING_AT" | "STOPPED_AT" | "IN_TRANSIT_TO";

export interface VehicleSnapshot {
  trip_id: string;
  route_id: string;
  direction: "N" | "S" | null;
  headsign: string | null;
  stop_id: string | null;
  station_name: string | null;
  lat: number | null;
  lon: number | null;
  location_status: LocationStatus | null;
  has_delay_alert: boolean;
  last_position_update: string | null;
}

export interface ServiceAlert {
  id: string;
  header_text: string;
  routes: string[];
  starts_at: string | null;
  ends_at: string | null;
}

export interface AlertsByRoute {
  route: string;
  count: number;
}

export interface IngestRun {
  started_at: string | null;
  finished_at: string | null;
  vehicle_count: number;
  alert_count: number;
  status: "running" | "success" | "error";
  error_message: string | null;
}

export interface HealthResponse {
  status: string;
  last_ingest_run: IngestRun | null;
}
