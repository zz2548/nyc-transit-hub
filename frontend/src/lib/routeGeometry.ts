// Flat-earth scale constants at NYC latitude (~40.7°)
const LAT_M = 111_000;
const LON_M = 111_000 * Math.cos((40.7 * Math.PI) / 180);

/**
 * Map API route IDs that don't appear on the official MTA diagram to their
 * canonical display names.
 *   6X / 7X  — express variants, same line on the map
 *   FX       — F express variant
 *   GS / FS / H — the three S shuttles (42 St, Franklin Av, Rockaway Park)
 */
export const ROUTE_CANONICAL: Record<string, string> = {
  "6X": "6",
  "7X": "7",
  "FX": "F",
  "GS": "S",
  "FS": "S",
  "H":  "S",
};

export function canonicalRouteId(routeId: string): string {
  return ROUTE_CANONICAL[routeId.toUpperCase()] ?? routeId.toUpperCase();
}

/**
 * Pixel offset slot per route. Half-integer values center even-count groups.
 * Multiply by LINE_WEIGHT (px) to get the final pixel offset for the plugin.
 *
 * Groups are chosen so adjacent slots differ by 1, giving touching lines with
 * no gap when rendered at LINE_WEIGHT px per route.
 */
// IND 6th Ave (B/D/F/M) and BMT Broadway (N/Q/R/W) share corridors in Queens
// and Brooklyn. Assigning the same half-integer slots to both families causes
// their lines to render on top of each other. Give all eight a globally unique
// slot so they spread out correctly on shared segments.
const ROUTE_SLOTS: Record<string, number> = {
  // IRT 7th Ave / Broadway
  "1": -1, "2": 0, "3": 1,
  // IRT Lex Ave
  "4": -1, "5": 0, "6": 1,
  // IRT Flushing (merged — single line)
  "7": 0,
  // IND 8th Ave
  "A": -1, "C": 0, "E": 1,
  // IND 6th Ave + BMT Broadway combined (8 unique slots, -3.5 → +3.5)
  "B": -3.5, "D": -2.5, "F": -1.5, "M": -0.5,
  "N":  0.5, "Q":  1.5, "R":  2.5, "W":  3.5,
  // BMT Nassau
  "J": -0.5, "Z": 0.5,
  // Singles
  "L": 0, "G": 0, "SIR": 0, "S": 0,
};

/** Pixel offset slot for a route (multiply by line weight to get px offset). */
export function routeOffsetSlot(routeId: string): number {
  return ROUTE_SLOTS[routeId.toUpperCase()] ?? 0;
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
