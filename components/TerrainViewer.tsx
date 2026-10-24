"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  TerrainColorMode,
  computeValueRange,
  valueToColor,
} from "@/lib/terrainColors";
import CriteriaStrip from "@/components/CriteriaStrip";
import {
  MoonbasePhase,
  MoonbaseSettings,
  PickMode,
} from "@/lib/api";
import {
  CriterionId,
  MARK_COLORS,
  SHADOW_LIT_FRACTION,
  activeCriteria,
  gapSentence,
  missionSummary,
  phaseLine,
  routeMarkAt,
} from "@/lib/moonbaseDisplay";
import {
  CellHoverInfo,
  describeHoverCell,
  TerrainAnalysisGrids,
} from "@/lib/routeValidation";

const TerrainScene3D = dynamic(() => import("./TerrainScene3D"), {
  ssr: false,
  loading: () => <div className="terrain-viewport-loading">Loading 3D terrain…</div>,
});

export interface RouteOverlay {
  route: number[][];
  color: string;
  label?: string;
}

export type ViewMode = "2d" | "3d";
export type MapLayer = TerrainColorMode;

interface TerrainViewerProps {
  terrainGrid: number[][] | null;
  hillshade?: number[][] | null;
  hazardGrid?: number[][] | null;
  illuminationGrid?: number[][] | null;
  psrGrid?: boolean[][] | null;
  commsGrid?: boolean[][] | null;
  keepoutGrid?: boolean[][] | null;
  route?: number[][];
  routeOverlays?: RouteOverlay[];
  start?: [number, number];
  goal?: [number, number];
  analysis?: TerrainAnalysisGrids | null;
  interactive?: boolean;
  pickMode?: PickMode;
  onCellClick?: (row: number, col: number) => void;
  loading?: boolean;
  previewError?: string | null;
  hero?: boolean;
  showLayerTabs?: boolean;
  showRoutes?: boolean;
  animateRoute?: boolean;
  title?: string;
  subtitle?: string;
  initialLayer?: MapLayer;
  initialViewMode?: ViewMode;
  moonbase?: MoonbaseSettings | null;
  phaseInfo?: MoonbasePhase | null;
  resolutionM?: number;
  maxSlopeDeg?: number;
  functionalGaps?: string[];
}

const LAYERS: {
  id: MapLayer;
  label: string;
  needsHazard?: boolean;
}[] = [
  { id: "hillshade", label: "Surface" },
  { id: "elevation", label: "Elevation" },
  { id: "hazard", label: "Hazard", needsHazard: true },
];

function strokePolyline(
  ctx: CanvasRenderingContext2D,
  points: number[][],
  cellWidth: number,
  cellHeight: number,
  color: string,
  lineWidth: number,
  withOutline = false,
  glow = false
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

  if (glow) {
    drawPath();
    ctx.strokeStyle = "rgba(0, 255, 255, 0.35)";
    ctx.lineWidth = lineWidth + 6;
    ctx.stroke();
  }

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

function mixRgb(
  base: [number, number, number],
  tint: [number, number, number],
  alpha: number
): [number, number, number] {
  return [
    Math.round(base[0] * (1 - alpha) + tint[0] * alpha),
    Math.round(base[1] * (1 - alpha) + tint[1] * alpha),
    Math.round(base[2] * (1 - alpha) + tint[2] * alpha),
  ];
}

export default function TerrainViewer({
  terrainGrid,
  hillshade,
  hazardGrid,
  illuminationGrid,
  psrGrid,
  commsGrid,
  keepoutGrid,
  route,
  routeOverlays,
  start,
  goal,
  analysis,
  interactive = false,
  pickMode = "start",
  onCellClick,
  loading = false,
  previewError = null,
  hero = true,
  showLayerTabs = true,
  showRoutes = false,
  animateRoute = false,
  title,
  subtitle,
  initialLayer = "hillshade",
  initialViewMode = "2d",
  moonbase = null,
  phaseInfo = null,
  resolutionM = 20,
  maxSlopeDeg = 20,
  functionalGaps,
}: TerrainViewerProps) {
  const shellRef = useRef<HTMLDivElement>(null);
  const viewportRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const [layer, setLayer] = useState<MapLayer>(initialLayer);
  const [viewMode, setViewMode] = useState<ViewMode>(initialViewMode);
  const [renderSize, setRenderSize] = useState(600);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [hoverCell, setHoverCell] = useState<CellHoverInfo | null>(null);
  const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 });
  const [highlightCell, setHighlightCell] = useState<[number, number] | null>(null);
  const [routeProgress, setRouteProgress] = useState(1);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const dragRef = useRef<{ x: number; y: number; panX: number; panY: number } | null>(null);

  const criteria = useMemo(
    () => (moonbase ? activeCriteria(moonbase, maxSlopeDeg) : []),
    [moonbase, maxSlopeDeg]
  );
  const [enabled, setEnabled] = useState<Partial<Record<CriterionId, boolean>>>({});

  function overlayOn(id: CriterionId): boolean {
    return (
      layer === "hillshade" &&
      criteria.some((row) => row.id === id && row.spatial) &&
      enabled[id] !== false
    );
  }

  const displayGrid = layer === "hazard" && hazardGrid ? hazardGrid : terrainGrid;

  useEffect(() => {
    if (!animateRoute || !showRoutes) {
      setRouteProgress(1);
      return;
    }
    setRouteProgress(0);
    const startTime = performance.now();
    const duration = 1800;
    let frame = 0;
    function tick(now: number) {
      const t = Math.min(1, (now - startTime) / duration);
      setRouteProgress(t);
      if (t < 1) frame = requestAnimationFrame(tick);
    }
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [animateRoute, showRoutes, route, routeOverlays]);

  useEffect(() => {
    const viewport = viewportRef.current;
    if (!viewport) return;

    function updateSize() {
      const width = viewport!.getBoundingClientRect().width;
      const vh = window.innerHeight;
      const heroHeight = hero
        ? Math.min(vh * 0.56, width * 0.92, 1100)
        : width;
      const size = Math.round(Math.max(280, Math.min(width, heroHeight)));
      setRenderSize(size);
    }

    updateSize();
    const observer = new ResizeObserver(updateSize);
    observer.observe(viewport);
    window.addEventListener("resize", updateSize);
    return () => {
      observer.disconnect();
      window.removeEventListener("resize", updateSize);
    };
  }, [hero]);

  useEffect(() => {
    function onFullscreenChange() {
      setIsFullscreen(document.fullscreenElement === shellRef.current);
    }
    document.addEventListener("fullscreenchange", onFullscreenChange);
    return () => document.removeEventListener("fullscreenchange", onFullscreenChange);
  }, []);

  const draw2d = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas || !terrainGrid || !displayGrid?.length) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const logical = renderSize;
    canvas.width = logical * dpr;
    canvas.height = logical * dpr;
    canvas.style.width = `${logical}px`;
    canvas.style.height = `${logical}px`;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    const rows = terrainGrid.length;
    const cols = terrainGrid[0].length;
    const cellWidth = logical / cols;
    const cellHeight = logical / rows;

    ctx.save();
    ctx.fillStyle = "#07080f";
    ctx.fillRect(0, 0, logical, logical);
    ctx.translate(pan.x, pan.y);
    ctx.scale(zoom, zoom);

    const useHillshade = layer === "hillshade" && hillshade && hillshade.length > 0;
    const valueColorMode = layer === "hillshade" && !useHillshade ? "elevation" : layer;
    const numericGrid =
      layer === "hazard" && hazardGrid ? hazardGrid : terrainGrid;
    const range =
      (layer === "elevation" || layer === "hazard") && numericGrid
        ? computeValueRange(numericGrid, layer, analysis?.nodataMask)
        : { min: 0, max: 1 };

    const imageData = ctx.createImageData(cols, rows);
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const idx = (r * cols + c) * 4;
        if (analysis?.nodataMask[r]?.[c]) {
          imageData.data[idx] = 26;
          imageData.data[idx + 1] = 26;
          imageData.data[idx + 2] = 34;
          imageData.data[idx + 3] = 255;
          continue;
        }
        let rgb: [number, number, number];
        if (useHillshade) {
          const g = Math.round(40 + hillshade[r][c] * 185);
          rgb = [g, g, g];
        } else {
          const css = valueToColor(Number(displayGrid[r][c]), range.min, range.max, valueColorMode);
          const m = css.match(/\d+/g);
          rgb = [Number(m?.[0] ?? 0), Number(m?.[1] ?? 0), Number(m?.[2] ?? 0)];
        }
        if (layer === "hillshade") {
          const lit = illuminationGrid?.[r]?.[c];
          const inPsr = !!psrGrid?.[r]?.[c];
          if (
            overlayOn("lighting") &&
            lit != null &&
            Number(lit) < SHADOW_LIT_FRACTION &&
            !inPsr
          ) {
            rgb = [Math.round(rgb[0] * 0.42), Math.round(rgb[1] * 0.45), Math.round(rgb[2] * 0.55)];
          }
          if (overlayOn("psr") && inPsr) {
            rgb = mixRgb(rgb, [88, 28, 135], 0.55);
          }
          if (overlayOn("comms") && commsGrid?.[r]?.[c]) {
            rgb = mixRgb(rgb, [180, 83, 9], 0.2);
          }
        }
        imageData.data[idx] = rgb[0];
        imageData.data[idx + 1] = rgb[1];
        imageData.data[idx + 2] = rgb[2];
        imageData.data[idx + 3] = 255;
      }
    }

    const offscreen = document.createElement("canvas");
    offscreen.width = cols;
    offscreen.height = rows;
    offscreen.getContext("2d")!.putImageData(imageData, 0, 0);
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = "high";
    ctx.drawImage(offscreen, 0, 0, logical, logical);

    if (interactive && analysis) {
      for (let r = 0; r < rows; r++) {
        for (let c = 0; c < cols; c++) {
          if (analysis.blockedMask[r]?.[c] && !analysis.nodataMask[r]?.[c]) {
            ctx.fillStyle = "rgba(220, 50, 50, 0.22)";
            ctx.fillRect(c * cellWidth, r * cellHeight, cellWidth, cellHeight);
          }
        }
      }
    }

    if (highlightCell && analysis) {
      const [hr, hc] = highlightCell;
      ctx.strokeStyle = "rgba(255, 220, 0, 0.95)";
      ctx.lineWidth = 2 / zoom;
      ctx.strokeRect(hc * cellWidth, hr * cellHeight, cellWidth, cellHeight);
    }

    const routeOutline = layer !== "hillshade";
    const sliceRoute = (pts: number[][]) => {
      if (routeProgress >= 1) return pts;
      const n = Math.max(2, Math.floor(pts.length * routeProgress));
      return pts.slice(0, n);
    };

    if (showRoutes) {
      const markGrids = {
        illumination: illuminationGrid,
        psr: psrGrid,
        comms: commsGrid,
        keepout: keepoutGrid,
        resolutionM,
      };
      const paintRoute = (points: number[][], color: string) => {
        const sliced = sliceRoute(points);
        strokePolyline(ctx, sliced, cellWidth, cellHeight, color, 2.5, routeOutline, true);
        if (layer !== "hillshade" || sliced.length < 2) return;
        for (let i = 1; i < sliced.length; i++) {
          const mark = routeMarkAt(sliced[i][0], sliced[i][1], enabled, markGrids);
          if (!mark) continue;
          strokePolyline(
            ctx,
            [sliced[i - 1], sliced[i]],
            cellWidth,
            cellHeight,
            MARK_COLORS[mark],
            3.2,
            false,
            false
          );
        }
      };
      if (routeOverlays?.length) {
        for (const overlay of routeOverlays) {
          if (!overlay.route || overlay.route.length < 2) continue;
          paintRoute(overlay.route, overlay.color);
        }
      } else if (route && route.length > 1) {
        paintRoute(route, "#00ffff");
      }
    }

    const markerR = 6 / zoom;
    if (start) {
      ctx.fillStyle = "#22c55e";
      ctx.beginPath();
      ctx.arc((start[1] + 0.5) * cellWidth, (start[0] + 0.5) * cellHeight, markerR, 0, Math.PI * 2);
      ctx.fill();
    }
    if (goal) {
      ctx.fillStyle = "#ef4444";
      ctx.beginPath();
      ctx.arc((goal[1] + 0.5) * cellWidth, (goal[0] + 0.5) * cellHeight, markerR, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.restore();
  }, [
    terrainGrid,
    displayGrid,
    hillshade,
    illuminationGrid,
    psrGrid,
    commsGrid,
    keepoutGrid,
    layer,
    renderSize,
    analysis,
    interactive,
    highlightCell,
    route,
    routeOverlays,
    showRoutes,
    routeProgress,
    start,
    goal,
    zoom,
    pan,
    moonbase,
    criteria,
    enabled,
    resolutionM,
  ]);

  useEffect(() => {
    if (viewMode === "2d") draw2d();
  }, [viewMode, draw2d]);

  function screenToCell(clientX: number, clientY: number): [number, number] | null {
    const canvas = canvasRef.current;
    if (!canvas || !terrainGrid) return null;
    const rect = canvas.getBoundingClientRect();
    const logicalX = (clientX - rect.left - pan.x) / zoom;
    const logicalY = (clientY - rect.top - pan.y) / zoom;
    const cols = terrainGrid[0].length;
    const rows = terrainGrid.length;
    const col = Math.floor((logicalX / renderSize) * cols);
    const row = Math.floor((logicalY / renderSize) * rows);
    if (row >= 0 && row < rows && col >= 0 && col < cols) return [row, col];
    return null;
  }

  function handlePointerDown(e: React.PointerEvent) {
    if (viewMode !== "2d") return;
    if (interactive && !e.shiftKey) return;
    dragRef.current = { x: e.clientX, y: e.clientY, panX: pan.x, panY: pan.y };
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
  }

  function handlePointerMove(e: React.PointerEvent) {
    if (!terrainGrid || !analysis) return;

    if (dragRef.current && viewMode === "2d" && !interactive) {
      setPan({
        x: dragRef.current.panX + (e.clientX - dragRef.current.x),
        y: dragRef.current.panY + (e.clientY - dragRef.current.y),
      });
      return;
    }

    const cell = screenToCell(e.clientX, e.clientY);
    if (!cell) {
      setHoverCell(null);
      setHighlightCell(null);
      return;
    }
    const [row, col] = cell;
    setHighlightCell([row, col]);
    setTooltipPos({ x: e.clientX, y: e.clientY });
    const hover = describeHoverCell(row, col, terrainGrid, analysis, start);
    if (layer === "hillshade") {
      if (overlayOn("psr") && psrGrid?.[row]?.[col]) {
        hover.message += " Permanently shadowed.";
      } else if (
        overlayOn("lighting") &&
        illuminationGrid &&
        Number(illuminationGrid[row]?.[col]) < SHADOW_LIT_FRACTION
      ) {
        hover.message += " In low-sun shadow.";
      }
      if (overlayOn("comms") && commsGrid?.[row]?.[col]) {
        hover.message += " No Earth view.";
      }
    }
    setHoverCell(hover);
  }

  function handlePointerUp() {
    dragRef.current = null;
  }

  function handleWheel(e: React.WheelEvent) {
    if (viewMode !== "2d") return;
    e.preventDefault();
    const factor = e.deltaY > 0 ? 0.92 : 1.08;
    setZoom((z) => Math.min(6, Math.max(0.5, z * factor)));
  }

  function handleClick(e: React.MouseEvent) {
    if (!interactive || !onCellClick) return;
    const cell = screenToCell(e.clientX, e.clientY);
    if (cell) onCellClick(cell[0], cell[1]);
  }

  function resetView() {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  }

  async function toggleFullscreen() {
    if (!shellRef.current) return;
    if (document.fullscreenElement) {
      await document.exitFullscreen();
    } else {
      await shellRef.current.requestFullscreen();
    }
  }

  const availableLayers = LAYERS.filter((item) => !item.needsHazard || !!hazardGrid);
  return (
    <div
      ref={shellRef}
      className={`terrain-viewer${hero ? " terrain-viewer-hero" : ""}${isFullscreen ? " terrain-viewer-fullscreen" : ""}`}
    >
      <div className="terrain-viewer-toolbar">
        <div className="terrain-viewer-titles">
          {title && <h2 className="terrain-viewer-title">{title}</h2>}
          {subtitle && <p className="terrain-viewer-subtitle">{subtitle}</p>}
        </div>
        <div className="terrain-viewer-controls">
          {showLayerTabs && (
            <div className="layer-tabs" role="tablist">
              {availableLayers.map((l) => (
                <button
                  key={l.id}
                  type="button"
                  role="tab"
                  aria-selected={layer === l.id}
                  className={`layer-tab${layer === l.id ? " active" : ""}`}
                  onClick={() => setLayer(l.id)}
                >
                  {l.label}
                </button>
              ))}
            </div>
          )}
          <div className="view-mode-tabs">
            <button
              type="button"
              className={`view-mode-btn${viewMode === "2d" ? " active" : ""}`}
              onClick={() => setViewMode("2d")}
            >
              2D
            </button>
            <button
              type="button"
              className={`view-mode-btn${viewMode === "3d" ? " active" : ""}`}
              onClick={() => setViewMode("3d")}
            >
              3D
            </button>
          </div>
          {viewMode === "2d" && (
            <button type="button" className="map-tool-btn" onClick={resetView} title="Reset zoom">
              Reset
            </button>
          )}
          <button type="button" className="map-tool-btn" onClick={toggleFullscreen} title="Fullscreen">
            {isFullscreen ? "Exit" : "Full"}
          </button>
        </div>
      </div>

      <div ref={viewportRef} className="terrain-viewport">
        {!terrainGrid || loading ? (
          <div className="terrain-viewport-loading">
            {loading ? (
              "Loading terrain…"
            ) : (
              <div className="terrain-empty-state">
                <p>No terrain data</p>
                {previewError ? (
                  <p className="terrain-empty-error">{previewError}</p>
                ) : (
                  <p className="terrain-empty-hint">
                    Start the backend:{" "}
                    <code>uvicorn api.main:app --reload --port 8000</code>
                  </p>
                )}
              </div>
            )}
          </div>
        ) : viewMode === "3d" ? (
          <TerrainScene3D
            terrainGrid={terrainGrid}
            displayGrid={displayGrid ?? terrainGrid}
            hillshade={hillshade}
            colorMode={layer}
            illuminationGrid={illuminationGrid}
            psrGrid={psrGrid}
            commsGrid={commsGrid}
            keepoutGrid={keepoutGrid}
            resolutionM={resolutionM}
            showLighting={overlayOn("lighting")}
            showPsr={overlayOn("psr")}
            showComms={overlayOn("comms")}
            showKeepout={overlayOn("keepout")}
            route={showRoutes ? route : undefined}
            routeOverlays={showRoutes ? routeOverlays : undefined}
            start={start}
            goal={goal}
            analysis={analysis}
            interactive={interactive}
            onCellClick={onCellClick}
            routeProgress={routeProgress}
            size={renderSize}
          />
        ) : (
          <canvas
            ref={canvasRef}
            className={`terrain-canvas-2d${interactive ? " interactive" : ""}`}
            style={{
              cursor: interactive
                ? "crosshair"
                : dragRef.current
                  ? "grabbing"
                  : "grab",
            }}
            onClick={handleClick}
            onPointerDown={handlePointerDown}
            onPointerMove={handlePointerMove}
            onPointerUp={handlePointerUp}
            onPointerLeave={() => {
              handlePointerUp();
              setHoverCell(null);
              setHighlightCell(null);
            }}
            onWheel={handleWheel}
          />
        )}

        {interactive && (
          <div
            className={`pick-mode-float${pickMode === "goal" ? " goal" : ""}`}
          >
            {`Placing Point ${pickMode === "start" ? "A" : "B"}`}
          </div>
        )}

        {hoverCell && analysis && (
          <div
            className={`map-tooltip terrain-hover-tooltip ${hoverCell.passable ? "ok" : "warn"}`}
            style={{ left: tooltipPos.x + 14, top: tooltipPos.y + 14 }}
          >
            <strong>
              Row {hoverCell.row}, Col {hoverCell.col}
            </strong>
            <div>{hoverCell.message}</div>
          </div>
        )}
      </div>

      {moonbase && (
        <CriteriaStrip
          phaseLine={phaseLine(phaseInfo, moonbase.phase)}
          missionLine={missionSummary(moonbase.mission)}
          gaps={gapSentence(functionalGaps)}
          rows={criteria}
          enabled={enabled}
          onToggle={(id) =>
            setEnabled((current) => ({ ...current, [id]: current[id] === false }))
          }
        />
      )}

      <p className="terrain-viewer-hint">
        {viewMode === "3d"
          ? "Drag to orbit · scroll to zoom · click to pick points"
          : interactive
            ? "Click to set points · Shift+drag to pan · scroll to zoom · hover for details"
            : "Scroll to zoom · drag to pan · hover for details · switch layers above"}
      </p>
    </div>
  );
}
