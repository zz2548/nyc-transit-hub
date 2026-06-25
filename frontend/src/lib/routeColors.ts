const ROUTE_COLOR_HEX: Record<string, string> = {
  "1": "#ee352e", "2": "#ee352e", "3": "#ee352e",
  "4": "#00933c", "5": "#00933c", "6": "#00933c", "6X": "#00933c",
  "7": "#b933ad", "7X": "#b933ad",
  "A": "#0039a6", "C": "#0039a6", "E": "#0039a6",
  "B": "#ff6319", "D": "#ff6319", "F": "#ff6319", "FX": "#ff6319", "M": "#ff6319",
  "G": "#6cbe45",
  "J": "#996633", "Z": "#996633",
  "L": "#a7a9ac",
  "N": "#fccc0a", "Q": "#fccc0a", "R": "#fccc0a", "W": "#fccc0a",
  "SI": "#0078c6", "SIR": "#0078c6",
  "GS": "#808183", "FS": "#808183", "H": "#808183", "S": "#808183",
};

export function routeColorHex(routeId: string): string {
  return ROUTE_COLOR_HEX[routeId.toUpperCase()] ?? "#888888";
}

const ROUTE_COLOR_VAR: Record<string, string> = {
  "1": "--line-irt-red",
  "2": "--line-irt-red",
  "3": "--line-irt-red",
  "4": "--line-irt-green",
  "5": "--line-irt-green",
  "6": "--line-irt-green",
  "7": "--line-irt-purple",
  S: "--line-shuttle-grey",
  GS: "--line-shuttle-grey",
  FS: "--line-shuttle-grey",
  H: "--line-shuttle-grey",
  A: "--line-ind-blue",
  C: "--line-ind-blue",
  E: "--line-ind-blue",
  B: "--line-ind-orange",
  D: "--line-ind-orange",
  F: "--line-ind-orange",
  M: "--line-ind-orange",
  G: "--line-ind-lightgreen",
  J: "--line-bmt-brown",
  Z: "--line-bmt-brown",
  N: "--line-bmt-yellow",
  Q: "--line-bmt-yellow",
  R: "--line-bmt-yellow",
  W: "--line-bmt-yellow",
  L: "--line-bmt-grey",
  SI: "--line-sir-blue",
  SIR: "--line-sir-blue",
};

/** Resolve a route id to a CSS custom property reference, e.g. "var(--line-irt-red)". */
export function routeColorVar(routeId: string): string {
  const variable = ROUTE_COLOR_VAR[routeId.toUpperCase()] ?? "--text-dim";
  return `var(${variable})`;
}

/** Routes painted on dark backgrounds need light text; a couple of the
 * MTA's official colors (yellow, light green) are bright enough that black
 * text reads better inside the bullet itself.
 */
const DARK_TEXT_ROUTES = new Set(["N", "Q", "R", "W", "G"]);

export function routeTextColor(routeId: string): string {
  return DARK_TEXT_ROUTES.has(routeId.toUpperCase()) ? "#0b0b0c" : "#ffffff";
}
