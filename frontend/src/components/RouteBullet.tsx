import { routeColorVar, routeTextColor } from "../lib/routeColors";

interface RouteBulletProps {
  routeId: string;
  size?: number;
}

export function RouteBullet({ routeId, size = 22 }: RouteBulletProps) {
  return (
    <span
      className="route-bullet"
      style={{
        width: size,
        height: size,
        fontSize: size * 0.55,
        background: routeColorVar(routeId),
        color: routeTextColor(routeId),
      }}
    >
      {routeId}
    </span>
  );
}
