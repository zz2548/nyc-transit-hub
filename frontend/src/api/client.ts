import type {
  AlertsByRoute,
  HealthResponse,
  ServiceAlert,
  Station,
  VehicleSnapshot,
} from "../types";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`);
  if (!response.ok) {
    throw new Error(`Request to ${path} failed with status ${response.status}`);
  }
  return (await response.json()) as T;
}

export const api = {
  health: () => getJson<HealthResponse>("/api/health"),
  stations: () => getJson<Station[]>("/api/stations"),
  vehicles: () => getJson<VehicleSnapshot[]>("/api/vehicles"),
  alerts: () => getJson<ServiceAlert[]>("/api/alerts"),
  alertsByRoute: () => getJson<AlertsByRoute[]>("/api/stats/alerts-by-route"),
};
