// Flat-earth scale constants at NYC latitude (~40.7°)
const LAT_M = 111_000;
const LON_M = 111_000 * Math.cos((40.7 * Math.PI) / 180);

/**
 * Pixel offset slots per route. Routes that share a physical corridor get
 * sequential slots so they render as side-by-side stripes rather than stacking.
 * Positive = right-hand side when traveling in the shape's forward direction.
 */
const ROUTE_SLOTS: Record<string, number> = {
  // IRT 7th Ave / Broadway: 1 local, 2/3 express
  "1": -2, "2": 0, "3": 2,
  // IRT Lex Ave: 4/5 express, 6 local
  "4": -2, "5": 0, "6": 2, "6X": 2,
  // IRT Flushing
  "7": -1, "7X": 1,
  // IND 8th Ave
  "A": -2, "C": 0, "E": 2,
  // IND 6th Ave / Concourse
  "B": -3, "D": -1, "F": 1, "FX": 1, "M": 3,
  // BMT Broadway
  "N": -3, "Q": -1, "R": 1, "W": 3,
  // BMT Nassau
  "J": -1, "Z": 1,
  // Singles — no offset needed
  "L": 0, "G": 0, "SI": 0, "GS": 0, "FS": 0, "H": 0,
};

const SLOT_METERS = 6;

/** Meters to offset this route perpendicular to its direction of travel. */
export function routeOffsetMeters(routeId: string): number {
  const slot = ROUTE_SLOTS[routeId.toUpperCase()] ?? 0;
  return slot * SLOT_METERS;
}

/**
 * Shift every point of a polyline perpendicularly by `offsetMeters`.
 * Positive = left when travelling forward (i.e. CCW rotation of the tangent).
 */
export function offsetPolyline(
  points: [number, number][],
  offsetMeters: number,
): [number, number][] {
  if (offsetMeters === 0 || points.length < 2) return points;

  return points.map((pt, i) => {
    const prev = points[Math.max(0, i - 1)];
    const next = points[Math.min(points.length - 1, i + 1)];

    // Tangent vector in metres
    const dlat = (next[0] - prev[0]) * LAT_M;
    const dlon = (next[1] - prev[1]) * LON_M;
    const len = Math.hypot(dlat, dlon);
    if (len < 0.001) return pt;

    // Perpendicular (CCW 90°): (-dlon, dlat)
    const perpLat = (-dlon / len) * (offsetMeters / LAT_M);
    const perpLon = (dlat / len) * (offsetMeters / LON_M);
    return [pt[0] + perpLat, pt[1] + perpLon] as [number, number];
  });
}

/**
 * Find the geographic bearing (0° = north, clockwise) at the point on a
 * polyline closest to (stationLat, stationLon). Averages a small window of
 * segments around the closest point for a smoother heading estimate.
 */
export function bearingAtStation(
  stationLat: number,
  stationLon: number,
  points: [number, number][],
): number {
  if (points.length < 2) return 0;

  let bestI = 0;
  let bestDist = Infinity;
  for (let i = 0; i < points.length - 1; i++) {
    const midLat = (points[i][0] + points[i + 1][0]) / 2;
    const midLon = (points[i][1] + points[i + 1][1]) / 2;
    const d = Math.hypot(
      (stationLat - midLat) * LAT_M,
      (stationLon - midLon) * LON_M,
    );
    if (d < bestDist) { bestDist = d; bestI = i; }
  }

  // Average tangent over a small window for smoothness
  const start = Math.max(0, bestI - 1);
  const end = Math.min(points.length - 1, bestI + 2);
  const dlat = (points[end][0] - points[start][0]) * LAT_M;
  const dlon = (points[end][1] - points[start][1]) * LON_M;
  return ((Math.atan2(dlon, dlat) * 180) / Math.PI + 360) % 360;
}

/**
 * Pick the shape polyline for a route+direction pair.
 * MTA shape_ids encode direction as the character after '..':
 *   N/S for most lines; W/E for east-west lines (L, 7, etc.).
 * The real-time feed maps "N" → geographic N or toward-Manhattan-W,
 * and "S" → geographic S or away-from-Manhattan-E.
 */
export function shapePointsForVehicle(
  routeId: string,
  direction: "N" | "S",
  shapes: { route_id: string; shape_id: string; points: [number, number][] }[],
): [number, number][] | null {
  const candidates = shapes.filter((s) => s.route_id === routeId);
  if (!candidates.length) return null;

  const wantedChars = direction === "N" ? ["N", "W"] : ["S", "E"];
  const matched = candidates.filter((s) => {
    const m = s.shape_id.match(/\.\.([NSEW])/);
    return m && wantedChars.includes(m[1]);
  });

  // Prefer matched shapes; fall back to all shapes for this route.
  // Among candidates pick the longest (most complete coverage).
  const pool = matched.length ? matched : candidates;
  return pool.reduce((best, s) =>
    s.points.length > best.points.length ? s : best,
  ).points;
}

/** Sample a lat/lon point and compass bearing at `fraction` ∈ [0,1] along a polyline. */
export function samplePolylineAt(
  points: [number, number][],
  fraction: number,
): { point: [number, number]; bearing: number } {
  if (points.length < 2) return { point: points[0], bearing: 0 };

  // Pre-compute cumulative lengths
  const segLens: number[] = [];
  let total = 0;
  for (let i = 0; i < points.length - 1; i++) {
    const dlat = (points[i + 1][0] - points[i][0]) * LAT_M;
    const dlon = (points[i + 1][1] - points[i][1]) * LON_M;
    const l = Math.hypot(dlat, dlon);
    segLens.push(l);
    total += l;
  }

  const target = fraction * total;
  let cum = 0;
  for (let i = 0; i < segLens.length; i++) {
    if (cum + segLens[i] >= target || i === segLens.length - 1) {
      const t = segLens[i] > 0 ? (target - cum) / segLens[i] : 0;
      const pt: [number, number] = [
        points[i][0] + t * (points[i + 1][0] - points[i][0]),
        points[i][1] + t * (points[i + 1][1] - points[i][1]),
      ];
      const dlat = (points[i + 1][0] - points[i][0]) * LAT_M;
      const dlon = (points[i + 1][1] - points[i][1]) * LON_M;
      const bearing = ((Math.atan2(dlon, dlat) * 180) / Math.PI + 360) % 360;
      return { point: pt, bearing };
    }
    cum += segLens[i];
  }
  return { point: points[points.length - 1], bearing: 0 };
}
