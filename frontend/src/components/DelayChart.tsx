import * as d3 from "d3";
import { useEffect, useRef } from "react";
import { routeColorVar } from "../lib/routeColors";
import type { AlertsByRoute } from "../types";

interface DelayChartProps {
  data: AlertsByRoute[];
}

const MARGIN = { top: 8, right: 28, bottom: 8, left: 36 };
const BAR_HEIGHT = 22;
const BAR_GAP = 8;

export function DelayChart({ data }: DelayChartProps) {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const svg = svgRef.current;
    const container = containerRef.current;
    if (!svg || !container) return;

    const render = () => {
      const width = container.clientWidth;
      const rows = data.slice(0, 10); // keep the chart legible -- top 10 affected routes
      const height = rows.length * (BAR_HEIGHT + BAR_GAP) + MARGIN.top + MARGIN.bottom;

      const selection = d3.select(svg).attr("width", width).attr("height", height);
      selection.selectAll("*").remove();

      if (rows.length === 0) {
        selection
          .append("text")
          .attr("x", width / 2)
          .attr("y", height / 2 || 40)
          .attr("text-anchor", "middle")
          .attr("class", "chart-empty-label")
          .text("No active alerts to chart");
        return;
      }

      const innerWidth = width - MARGIN.left - MARGIN.right;
      const maxCount = d3.max(rows, (d) => d.count) ?? 1;
      const x = d3.scaleLinear().domain([0, maxCount]).range([0, innerWidth]);

      const group = selection.append("g").attr("transform", `translate(${MARGIN.left},${MARGIN.top})`);

      const row = group
        .selectAll("g.row")
        .data(rows)
        .join("g")
        .attr("class", "row")
        .attr("transform", (_, i) => `translate(0,${i * (BAR_HEIGHT + BAR_GAP)})`);

      row
        .append("rect")
        .attr("x", 0)
        .attr("y", 0)
        .attr("height", BAR_HEIGHT)
        .attr("rx", 3)
        .attr("width", (d) => Math.max(2, x(d.count)))
        .style("fill", (d) => routeColorVar(d.route));

      row
        .append("text")
        .attr("x", -10)
        .attr("y", BAR_HEIGHT / 2)
        .attr("dy", "0.32em")
        .attr("text-anchor", "end")
        .attr("class", "chart-route-label")
        .text((d) => d.route);

      row
        .append("text")
        .attr("x", (d) => Math.max(2, x(d.count)) + 8)
        .attr("y", BAR_HEIGHT / 2)
        .attr("dy", "0.32em")
        .attr("class", "chart-count-label")
        .text((d) => d.count);
    };

    render();
    const observer = new ResizeObserver(render);
    observer.observe(container);
    return () => observer.disconnect();
  }, [data]);

  return (
    <section className="panel chart-panel" aria-label="Active alerts by route">
      <h2 className="panel__eyebrow">ALERTS BY ROUTE</h2>
      <div ref={containerRef} className="chart-panel__canvas">
        <svg ref={svgRef} role="img" aria-label="Bar chart of active alerts by subway route" />
      </div>
    </section>
  );
}
