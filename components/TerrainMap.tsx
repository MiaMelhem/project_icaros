"use client";

import { useEffect, useRef, useState } from "react";
import {
  CellHoverInfo,
  describeHoverCell,
  TerrainAnalysisGrids,
} from "@/lib/routeValidation";

interface RouteOverlay {
  route: number[][];
  color: string;
  label?: string;
}

interface TerrainMapProps {
  grid: number[][] | null;
  hillshade?: number[][] | null;
  route?: number[][];
  routeOverlays?: RouteOverlay[];
  start?: [number, number];
  goal?: [number, number];
  title: string;
  colorMode?: "elevation" | "hazard" | "hillshade";
  displaySize?: number;
  responsive?: boolean;
  interactive?: boolean;
  pickMode?: "start" | "goal";
  analysis?: TerrainAnalysisGrids | null;
  onCellClick?: (row: number, col: number) => void;
  loading?: boolean;
  featured?: boolean;
}

function valueToColor(
  value: number,
  min: number,
  max: number,
  colorMode: string
): string {
  const range = max - min || 1;
  const t = (value - min) / range;

  if (colorMode === "hazard") {
    const r = Math.round(255 * t);
    const g = Math.round(255 * (1 - t));
    return `rgb(${r},${g},50)`;
  }

  if (t < 0.25) {
    const s = t / 0.25;
    return `rgb(0,${Math.round(100 + 155 * s)},${Math.round(255 - 100 * s)})`;
  }
  if (t < 0.5) {
    const s = (t - 0.25) / 0.25;
    return `rgb(${Math.round(255 * s)},255,${Math.round(155 - 155 * s)})`;
  }
  if (t < 0.75) {
    const s = (t - 0.5) / 0.25;
    return `rgb(255,${Math.round(255 - 100 * s)},0)`;
  }
  const s = (t - 0.75) / 0.25;
  return `rgb(255,${Math.round(155 - 155 * s)},0)`;
}

function hillshadeToColor(shade: number): string {
  const gray = Math.round(40 + shade * 185);
  return `rgb(${gray},${gray},${gray})`;
}

function strokePolyline(
  ctx: CanvasRenderingContext2D,
  points: number[][],
  cellWidth: number,
  cellHeight: number,
  color: string,
  lineWidth: number,
  withOutline = false
) {
  if (points.length < 2) return;

  const drawPath = () => {
    ctx.beginPath();
    for (let i = 0; i < points.length; i++) {
      const x = (points[i][1] + 0.5) * cellWidth;
      const y = (points[i][0] + 0.5) * cellHeight;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
  };

  if (withOutline) {
    drawPath();
    ctx.strokeStyle = "rgba(0, 0, 0, 0.75)";
    ctx.lineWidth = lineWidth + 2.5;
    ctx.lineJoin = "round";
    ctx.lineCap = "round";
    ctx.stroke();
  }

  drawPath();
  ctx.strokeStyle = color;
  ctx.lineWidth = lineWidth;
  ctx.lineJoin = "round";
  ctx.lineCap = "round";
  ctx.stroke();
}

function cellFromEvent(
  event: React.MouseEvent<HTMLCanvasElement>,
  grid: number[][],
  canvas: HTMLCanvasElement
): [number, number] | null {
  const rect = canvas.getBoundingClientRect();
  const x = event.clientX - rect.left;
  const y = event.clientY - rect.top;
  const cols = grid[0].length;
  const rows = grid.length;
  const col = Math.floor((x / rect.width) * cols);
  const row = Math.floor((y / rect.height) * rows);
  if (row >= 0 && row < rows && col >= 0 && col < cols) {
    return [row, col];
  }
  return null;
}

export default function TerrainMap({
  grid,
  hillshade,
  route,
  routeOverlays,
  start,
  goal,
  title,
  colorMode = "elevation",
  displaySize = 360,
  responsive = false,
  interactive = false,
  pickMode = "start",
  analysis = null,
  onCellClick,
  loading = false,
  featured = false,
}: TerrainMapProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [hoverCell, setHoverCell] = useState<CellHoverInfo | null>(null);
  const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 });
  const [highlightCell, setHighlightCell] = useState<[number, number] | null>(null);
  const [measuredSize, setMeasuredSize] = useState(displaySize);

  useEffect(() => {
    if (!responsive) {
      setMeasuredSize(displaySize);
      return;
    }

    const container = containerRef.current;
    if (!container) return;

    const updateSize = () => {
      const width = container.getBoundingClientRect().width;
      const size = Math.round(Math.max(220, Math.min(width, 800)));
      setMeasuredSize(size);
    };

    updateSize();
    const observer = new ResizeObserver(updateSize);
    observer.observe(container);
    return () => observer.disconnect();
  }, [responsive, displaySize]);

  const renderSize = responsive ? measuredSize : displaySize;
  const routeOutline = colorMode === "elevation" || colorMode === "hazard";

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !grid || grid.length === 0) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const rows = grid.length;
    const cols = grid[0].length;
    canvas.width = renderSize;
    canvas.height = renderSize;

    const cellWidth = renderSize / cols;
    const cellHeight = renderSize / rows;

    const useHillshade = colorMode === "hillshade" && hillshade && hillshade.length > 0;
    const valueColorMode =
      colorMode === "hillshade" && !useHillshade ? "elevation" : colorMode;

    let min = Infinity;
    let max = -Infinity;
    if (valueColorMode === "elevation" || valueColorMode === "hazard") {
      for (let r = 0; r < rows; r++) {
        for (let c = 0; c < cols; c++) {
          if (analysis?.nodataMask[r]?.[c]) continue;
          const val = grid[r][c];
          if (!Number.isFinite(val)) continue;
          if (val < min) min = val;
          if (val > max) max = val;
        }
      }
      if (!Number.isFinite(min)) {
        min = 0;
        max = 1;
      }
    }

    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        if (analysis?.nodataMask[r]?.[c]) {
          ctx.fillStyle = "#1a1a22";
          ctx.fillRect(c * cellWidth, r * cellHeight, cellWidth + 0.5, cellHeight + 0.5);
          continue;
        }

        if (useHillshade) {
          ctx.fillStyle = hillshadeToColor(hillshade[r][c]);
        } else {
          ctx.fillStyle = valueToColor(grid[r][c], min, max, valueColorMode);
        }
        ctx.fillRect(c * cellWidth, r * cellHeight, cellWidth + 0.5, cellHeight + 0.5);

        if (interactive && analysis?.blockedMask[r]?.[c] && !analysis.nodataMask[r]?.[c]) {
          ctx.fillStyle = "rgba(220, 50, 50, 0.25)";
          ctx.fillRect(c * cellWidth, r * cellHeight, cellWidth + 0.5, cellHeight + 0.5);
        }
      }
    }

    if (highlightCell && interactive) {
      const [hr, hc] = highlightCell;
      ctx.strokeStyle = "rgba(255, 220, 0, 0.9)";
      ctx.lineWidth = 2;
      ctx.strokeRect(hc * cellWidth, hr * cellHeight, cellWidth, cellHeight);
    }

    if (routeOverlays && routeOverlays.length > 0) {
      for (const overlay of routeOverlays) {
        if (!overlay.route || overlay.route.length < 2) continue;
        strokePolyline(
          ctx,
          overlay.route,
          cellWidth,
          cellHeight,
          overlay.color,
          2.5,
          routeOutline
        );
      }
    } else if (route && route.length > 1) {
      strokePolyline(
        ctx,
        route,
        cellWidth,
        cellHeight,
        "#00ffff",
        2,
        routeOutline
      );
    }

    if (start) {
      ctx.fillStyle = "#00ff00";
      ctx.beginPath();
      ctx.arc(
        (start[1] + 0.5) * cellWidth,
        (start[0] + 0.5) * cellHeight,
        5,
        0,
        Math.PI * 2
      );
      ctx.fill();
      ctx.strokeStyle = "#004400";
      ctx.lineWidth = 1;
      ctx.stroke();
    }

    if (goal) {
      ctx.fillStyle = "#ff0000";
      ctx.beginPath();
      ctx.arc(
        (goal[1] + 0.5) * cellWidth,
        (goal[0] + 0.5) * cellHeight,
        5,
        0,
        Math.PI * 2
      );
      ctx.fill();
      ctx.strokeStyle = "#440000";
      ctx.lineWidth = 1;
      ctx.stroke();
    }
  }, [
    grid,
    hillshade,
    route,
    routeOverlays,
    start,
    goal,
    colorMode,
    renderSize,
    analysis,
    interactive,
    highlightCell,
  ]);

  function handleMouseMove(event: React.MouseEvent<HTMLCanvasElement>) {
    if (!interactive || !grid || !analysis) {
      setHoverCell(null);
      setHighlightCell(null);
      return;
    }

    const canvas = canvasRef.current;
    if (!canvas) return;

    const cell = cellFromEvent(event, grid, canvas);
    if (!cell) {
      setHoverCell(null);
      setHighlightCell(null);
      return;
    }

    const [row, col] = cell;
    setHighlightCell([row, col]);
    setTooltipPos({ x: event.clientX, y: event.clientY });
    setHoverCell(describeHoverCell(row, col, grid, analysis, start));
  }

  function handleMouseLeave() {
    setHoverCell(null);
    setHighlightCell(null);
  }

  function handleClick(event: React.MouseEvent<HTMLCanvasElement>) {
    if (!interactive || !onCellClick || !grid) return;

    const canvas = canvasRef.current;
    if (!canvas) return;

    const cell = cellFromEvent(event, grid, canvas);
    if (cell) {
      onCellClick(cell[0], cell[1]);
    }
  }

  return (
    <div
      className={`map-panel${featured ? " map-panel-featured" : ""}${responsive ? " map-panel-responsive" : ""}`}
    >
      <h3>{title}</h3>
      {!grid ? (
        <div
          className={`map-placeholder${loading ? " loading-pulse" : ""}${responsive ? " map-placeholder-responsive" : ""}`}
          style={responsive ? undefined : { width: displaySize, height: displaySize }}
        >
          {loading ? "Loading terrain…" : "No terrain data"}
        </div>
      ) : (
        <>
          <div
            ref={containerRef}
            className={`map-canvas-wrap${responsive ? " map-canvas-wrap-responsive" : ""}`}
          >
            <canvas
              ref={canvasRef}
              onClick={handleClick}
              onMouseMove={handleMouseMove}
              onMouseLeave={handleMouseLeave}
              className={`map-canvas${interactive ? " interactive" : ""}${responsive ? " map-canvas-responsive" : ""}`}
              style={{
                cursor: interactive ? "crosshair" : "default",
              }}
            />
            {interactive && hoverCell && (
              <div
                className={`map-tooltip ${hoverCell.passable ? "ok" : "warn"}`}
                style={{ left: tooltipPos.x + 12, top: tooltipPos.y + 12 }}
              >
                <strong>
                  Row {hoverCell.row}, Col {hoverCell.col}
                </strong>
                <div>{hoverCell.message}</div>
              </div>
            )}
          </div>
          {interactive && (
            <p className="map-hint">
              Lunar hillshade · hover for details · click to set Point{" "}
              {pickMode === "start" ? "A" : "B"}. Red tint = too steep. Dark = no data.
            </p>
          )}
          {!interactive && colorMode === "elevation" && (
            <div className="map-legend" aria-hidden="true">
              <span className="legend-swatch legend-low" /> Low
              <span className="legend-swatch legend-mid" /> Mid
              <span className="legend-swatch legend-high" /> High
            </div>
          )}
          {!interactive && colorMode === "hazard" && (
            <div className="map-legend" aria-hidden="true">
              <span className="legend-swatch legend-safe" /> Safer
              <span className="legend-swatch legend-danger" /> Hazardous
            </div>
          )}
          {!interactive && (route || routeOverlays) && (
            <div className="map-legend map-legend-route" aria-hidden="true">
              <span className="legend-line" /> Route
              <span className="legend-dot start" /> A
              <span className="legend-dot goal" /> B
            </div>
          )}
        </>
      )}
    </div>
  );
}
