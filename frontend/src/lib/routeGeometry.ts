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

/** Ramer-Douglas-Peucker simplification in geographic (lat/lon) coordinates. */
function rdpSimplify(pts: [number, number][], eps: number): [number, number][] {
  if (pts.length <= 2) return pts;
  const [x1, y1] = pts[0], [x2, y2] = pts[pts.length - 1];
  const lineLen = Math.hypot(x2 - x1, y2 - y1);
  let maxDist = 0, maxIdx = 0;
  for (let i = 1; i < pts.length - 1; i++) {
    const [x, y] = pts[i];
    const dist = lineLen === 0
      ? Math.hypot(x - x1, y - y1)
      : Math.abs((y2 - y1) * x - (x2 - x1) * y + x2 * y1 - y2 * x1) / lineLen;
    if (dist > maxDist) { maxDist = dist; maxIdx = i; }
  }
  if (maxDist > eps) {
    const left  = rdpSimplify(pts.slice(0, maxIdx + 1), eps);
    const right = rdpSimplify(pts.slice(maxIdx), eps);
    return [...left.slice(0, -1), ...right];
  }
  return [pts[0], pts[pts.length - 1]];
}

/**
 * Clean a GTFS shape before passing to leaflet-polylineoffset.
 *
 * Root causes of the visible loops:
 *  A) The offset plugin uses miter joins. Dense point clusters produce
 *     near-zero-length segments whose miters become NaN/infinite → spikes.
 *  B) When offset px > curve radius px, the offset line self-intersects → loop.
 *     At zoom 14 with 10.5 px offset (~50 m) this happens on tight curves.
 *
 * Fixes applied in order:
 *  1. RDP simplification (ε ≈ 8 m) — removes redundant dense clusters while
 *     preserving the overall route geometry.
 *  2. Drop near-U-turn vertices (> 150°) — eliminates remaining miter spikes
 *     from near-180° direction reversals.
 *  3. Truncate backtracking tails — if the polyline's straight-line distance
 *     from the start begins falling well below the maximum reached, the GTFS
 *     shape has looped back (terminal wye/loop track). Keep only the prefix
 *     up to the furthest point.
 */
export function preprocessShape(points: [number, number][]): [number, number][] {
  if (points.length < 2) return points;

  // Pass 1 – RDP simplification (ε ≈ 8 m in degrees at NYC latitude)
  const simplified = rdpSimplify(points, 0.00007);
  if (simplified.length < 2) return simplified;

  // Pass 2 – drop near-U-turn vertices (> 150° turn)
  const noUturn: [number, number][] = [simplified[0]];
  for (let i = 1; i < simplified.length - 1; i++) {
    const ax = simplified[i - 1][1], ay = simplified[i - 1][0];
    const bx = simplified[i][1],     by = simplified[i][0];
    const cx = simplified[i + 1][1], cy = simplified[i + 1][0];
    const abA = Math.atan2(by - ay, bx - ax);
    const bcA = Math.atan2(cy - by, cx - bx);
    const turn = Math.abs(((bcA - abA + 3 * Math.PI) % (2 * Math.PI)) - Math.PI) * (180 / Math.PI);
    if (turn < 150) noUturn.push(simplified[i]);
  }
  noUturn.push(simplified[simplified.length - 1]);

  // Pass 3 – truncate backtracking tails (terminal loops).
  // Find the point furthest from the start. If the endpoint is substantially
  // closer to the start than that maximum (ratio < 0.55), the shape loops
  // back; keep only up to the furthest point.
  const [s0, s1] = noUturn[0];
  let maxDist = 0, maxIdx = 0;
  for (let i = 0; i < noUturn.length; i++) {
    const d = Math.hypot(noUturn[i][0] - s0, noUturn[i][1] - s1);
    if (d > maxDist) { maxDist = d; maxIdx = i; }
  }
  const endDist = Math.hypot(noUturn[noUturn.length - 1][0] - s0,
                              noUturn[noUturn.length - 1][1] - s1);
  if (maxIdx < noUturn.length - 5 && maxDist > 0 && endDist / maxDist < 0.55) {
    return noUturn.slice(0, maxIdx + 1);
  }
  return noUturn;
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
