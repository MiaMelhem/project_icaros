"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import MoonbaseControls from "@/components/MoonbaseControls";
import RouteControls, { RouteControlValues } from "@/components/RouteControls";
import TerrainViewer from "@/components/TerrainViewer";
import MetricsTable from "@/components/MetricsTable";
import RouteExport from "@/components/RouteExport";
import RouteComparisonDashboard from "@/components/RouteComparisonDashboard";
import DemUpload from "@/components/DemUpload";
import {
  DEFAULT_MOONBASE,
  fetchLunarSites,
  fetchMoonbase,
  fetchRovers,
  fetchTerrainPreview,
  moonbaseRequestFields,
  planRoute,
  compareRoutes,
  saveRun,
  MoonbaseCatalog,
  MoonbaseSettings,
  CoordinateInfo,
  CompareRoutesResponse,
  LunarSite,
  PickMode,
  PlanRouteResponse,
  RoverConfig,
  RouteValidationResult,
  TerrainMetadata,
  TerrainPreviewResponse,
} from "@/lib/api";
import { validateRouteClient, TerrainAnalysisGrids } from "@/lib/routeValidation";
import { isSupabaseConfigured } from "@/lib/supabaseClient";
import {
  PresetRoverMode,
  RoverMode,
  buildRoverApiFields,
  defaultCustomRover,
  deleteCustomRover,
  findBuiltinPreset,
  isPresetCustomized,
  loadCustomRovers,
  roverModeLabel,
  saveCustomRover,
} from "@/lib/customRovers";

const DEFAULT_CONTROLS: RouteControlValues = {
  terrainMode: "site",
  siteId: "shackleton-rim",
  terrainSize: 200,
  resolution: 20,
  startRow: 20,
  startCol: 20,
  goalRow: 170,
  goalCol: 170,
  hazardWeight: 5.0,
};

function previewToAnalysis(
  preview: TerrainPreviewResponse
): TerrainAnalysisGrids {
  return {
    slope: preview.slope,
    blockedMask: preview.blocked_mask,
    nodataMask: preview.nodata_mask,
    maxSlopeDeg: preview.max_slope_deg,
  };
}

function StepIndicator({
  hasPreview,
  hasResult,
  previewLoading,
}: {
  hasPreview: boolean;
  hasResult: boolean;
  previewLoading: boolean;
}) {
  const steps = [
    { label: "Load a map", done: hasPreview && !previewLoading },
    { label: "Place A and B", done: hasResult, active: hasPreview && !hasResult },
    { label: "Plan or compare", done: hasResult, active: hasPreview && !hasResult },
    { label: "Read the result", done: false, active: hasResult },
  ];
  const hint = previewLoading
    ? "The map is loading. You can change the site while you wait."
    : !hasPreview
      ? "Pick a site in the panel. The map appears when the terrain is ready."
      : hasResult
        ? "The path is on the map. Metrics and the CSV export are under it."
        : "Click the map to move A and B, then Plan this route. Compare rovers checks both vehicles on the same ground.";

  return (
    <div className="learn-bar">
      <ol className="step-indicator" aria-label="Workflow progress">
        {steps.map((step, i) => (
          <li
            key={step.label}
            className={`step${step.done ? " done" : ""}${step.active ? " active" : ""}`}
          >
            <span className="step-num">{step.done ? "✓" : i + 1}</span>
            {step.label}
          </li>
        ))}
      </ol>
      <p className="learn-hint">{hint}</p>
    </div>
  );
}

export default function Home() {
  const [builtinRovers, setBuiltinRovers] = useState<RoverConfig[]>([]);
  const [customRovers, setCustomRovers] = useState<RoverConfig[]>([]);
  const [roverMode, setRoverMode] = useState<RoverMode>("astrolab");
  const [activeRoverConfig, setActiveRoverConfig] = useState<RoverConfig | null>(null);
  const [presetOverrides, setPresetOverrides] = useState<
    Partial<Record<PresetRoverMode, RoverConfig>>
  >({});
  const [selectedSavedCustomName, setSelectedSavedCustomName] = useState("");
  const [roverSaveMessage, setRoverSaveMessage] = useState<string | null>(null);
  const [sites, setSites] = useState<LunarSite[]>([]);
  const [controls, setControls] = useState<RouteControlValues>(DEFAULT_CONTROLS);
  const [preview, setPreview] = useState<TerrainPreviewResponse | null>(null);
  const [previewMetadata, setPreviewMetadata] = useState<TerrainMetadata | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [result, setResult] = useState<PlanRouteResponse | null>(null);
  const [coordinates, setCoordinates] = useState<CoordinateInfo | null>(null);
  const [routeValidation, setRouteValidation] = useState<RouteValidationResult | null>(null);
  const [pickMode, setPickMode] = useState<PickMode>("start");
  const [loading, setLoading] = useState(false);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [moonbase, setMoonbase] = useState<MoonbaseSettings>(DEFAULT_MOONBASE);
  const [moonbaseCatalog, setMoonbaseCatalog] = useState<MoonbaseCatalog | null>(null);
  const [comparison, setComparison] = useState<CompareRoutesResponse | null>(null);
  const [compareLoading, setCompareLoading] = useState(false);
  const [selectedAlternativeId, setSelectedAlternativeId] = useState<string | null>(null);
  const [mobileControlsOpen, setMobileControlsOpen] = useState(false);
  const [isDesktopLayout, setIsDesktopLayout] = useState(true);
  const resultsRef = useRef<HTMLDivElement>(null);

  const astrolabPreset = useMemo(
    () => findBuiltinPreset("astrolab", builtinRovers),
    [builtinRovers]
  );
  const pegasusPreset = useMemo(
    () => findBuiltinPreset("pegasus", builtinRovers),
    [builtinRovers]
  );

  const currentPreset = useMemo(() => {
    if (roverMode === "astrolab") return astrolabPreset;
    if (roverMode === "pegasus") return pegasusPreset;
    return undefined;
  }, [roverMode, astrolabPreset, pegasusPreset]);

  const roverApiFields = useMemo(
    () => buildRoverApiFields(roverMode, activeRoverConfig, currentPreset),
    [roverMode, activeRoverConfig, currentPreset]
  );

  const isRoverDirty = useMemo(() => {
    if (roverMode === "custom") return true;
    return isPresetCustomized(
      roverMode,
      activeRoverConfig,
      roverMode === "astrolab" ? astrolabPreset : pegasusPreset
    );
  }, [roverMode, activeRoverConfig, astrolabPreset, pegasusPreset]);

  const roverAnalysisKey = activeRoverConfig
    ? `${roverMode}:${activeRoverConfig.max_slope_deg}:${activeRoverConfig.roughness_tolerance}`
    : roverMode;

  function scrollToResults() {
    requestAnimationFrame(() => {
      resultsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }

  const analysis = useMemo(
    () => (preview ? previewToAnalysis(preview) : null),
    [preview]
  );

  useEffect(() => {
    setCustomRovers(loadCustomRovers());

    fetchRovers()
      .then((loaded) => {
        setBuiltinRovers(loaded);
        const initial = findBuiltinPreset("astrolab", loaded);
        if (initial) {
          setActiveRoverConfig({ ...initial });
        }
      })
      .catch((err) => setError(`Failed to load rovers: ${err.message}`));

    fetchMoonbase()
      .then(setMoonbaseCatalog)
      .catch(() => setMoonbaseCatalog(null));

    fetchLunarSites()
      .then((loadedSites) => {
        setSites(loadedSites);
        if (loadedSites.length > 0) {
          setControls((prev) => ({
            ...prev,
            siteId: loadedSites.some((s) => s.id === prev.siteId)
              ? prev.siteId
              : loadedSites[0].id,
          }));
        }
      })
      .catch(() => setSites([]));
  }, []);

  function resolvePresetConfig(mode: PresetRoverMode): RoverConfig | null {
    const preset = mode === "astrolab" ? astrolabPreset : pegasusPreset;
    if (!preset) return null;
    return { ...(presetOverrides[mode] ?? preset) };
  }

  function handleRoverModeChange(mode: RoverMode) {
    setRoverMode(mode);
    setRoverSaveMessage(null);

    if (mode === "custom") {
      setActiveRoverConfig(defaultCustomRover());
      setSelectedSavedCustomName("");
      return;
    }

    const next = resolvePresetConfig(mode);
    if (next) setActiveRoverConfig(next);
  }

  function handlePresetConfigChange(mode: PresetRoverMode, config: RoverConfig) {
    setPresetOverrides((prev) => ({ ...prev, [mode]: config }));
    if (roverMode === mode) {
      setActiveRoverConfig({ ...config });
    }
  }

  function handleResetPreset(mode: PresetRoverMode) {
    setPresetOverrides((prev) => {
      const next = { ...prev };
      delete next[mode];
      return next;
    });

    const preset = mode === "astrolab" ? astrolabPreset : pegasusPreset;
    if (preset && roverMode === mode) {
      setActiveRoverConfig({ ...preset });
    }
  }

  function handleRoverConfigChange(config: RoverConfig) {
    setActiveRoverConfig(config);
    setRoverSaveMessage(null);
  }

  function handleLoadSavedCustom(name: string) {
    setSelectedSavedCustomName(name);
    setRoverSaveMessage(null);

    if (!name) {
      setActiveRoverConfig(defaultCustomRover());
      return;
    }

    const saved = customRovers.find((r) => r.name === name);
    if (saved) {
      setActiveRoverConfig({ ...saved });
    }
  }

  function handleSaveCustomRover() {
    if (!activeRoverConfig?.name.trim()) {
      setRoverSaveMessage("Enter a rover name before saving.");
      return;
    }

    const updated = saveCustomRover(activeRoverConfig);
    setCustomRovers(updated);
    setSelectedSavedCustomName(activeRoverConfig.name.trim());
    setRoverSaveMessage(`Saved "${activeRoverConfig.name.trim()}" to this browser.`);
  }

  function handleDeleteCustomRover() {
    if (!selectedSavedCustomName) return;
    const updated = deleteCustomRover(selectedSavedCustomName);
    setCustomRovers(updated);
    setRoverSaveMessage(`Deleted "${selectedSavedCustomName}".`);
    setSelectedSavedCustomName("");
    setActiveRoverConfig(defaultCustomRover());
  }

  const loadPreview = useCallback(async () => {
    if (!roverApiFields) return;

    setPreviewLoading(true);
    setPreviewError(null);

    try {
      const previewData = await fetchTerrainPreview({
        terrain_mode: controls.terrainMode,
        site_id: controls.terrainMode === "site" ? controls.siteId : undefined,
        terrain_size: controls.terrainSize,
        resolution_m_per_pixel: controls.resolution,
        ...roverApiFields,
        ...moonbaseRequestFields(moonbase),
      });
      setPreview(previewData);
      setPreviewMetadata(previewData.metadata);
      setError(null);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to load terrain preview";
      setPreviewError(message);
      setError(message);
    } finally {
      setPreviewLoading(false);
    }
  }, [
    controls.terrainMode,
    controls.siteId,
    controls.terrainSize,
    controls.resolution,
    roverAnalysisKey,
    roverApiFields,
    moonbase,
  ]);

  useEffect(() => {
    loadPreview();
  }, [loadPreview]);

  const start: [number, number] = [controls.startRow, controls.startCol];
  const goal: [number, number] = [controls.goalRow, controls.goalCol];

  useEffect(() => {
    if (!preview || !analysis) {
      setRouteValidation(null);
      return;
    }

    const validation = validateRouteClient(start, goal, preview.terrain, analysis, {
      maxRangeM: activeRoverConfig?.max_range_m,
      resolutionM: controls.resolution,
    });
    setRouteValidation({
      feasible: validation.feasible,
      reason_code: validation.reasonCode,
      message: validation.message,
    });
  }, [
    preview,
    analysis,
    start,
    goal,
    activeRoverConfig?.max_slope_deg,
    activeRoverConfig?.max_range_m,
    controls.resolution,
  ]);

  function handleMoonbaseChange(next: MoonbaseSettings) {
    setMoonbase(next);
    setResult(null);
    setComparison(null);
    setSelectedAlternativeId(null);
  }

  function handleCellClick(row: number, col: number) {
    if (pickMode === "start") {
      setControls((prev) => ({
        ...prev,
        startRow: row,
        startCol: col,
      }));
      setPickMode("goal");
    } else {
      setControls((prev) => ({
        ...prev,
        goalRow: row,
        goalCol: col,
      }));
    }
  }

  async function handleRun() {
    if (!roverApiFields || (routeValidation && !routeValidation.feasible)) {
      return;
    }

    setLoading(true);
    setError(null);
    setSaveMessage(null);
    setComparison(null);
    setSelectedAlternativeId(null);

    try {
      const response = await planRoute({
        terrain_mode: controls.terrainMode,
        site_id: controls.terrainMode === "site" ? controls.siteId : undefined,
        terrain_size: controls.terrainSize,
        resolution_m_per_pixel: controls.resolution,
        ...roverApiFields,
        start,
        goal,
        hazard_weight: controls.hazardWeight,
        ...moonbaseRequestFields(moonbase),
      });
      setResult(response);
      setCoordinates(response.coordinates ?? null);
      if (response.validation) {
        setRouteValidation(response.validation);
      }
      if (response.route_found) {
        scrollToResults();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
      setResult(null);
      setCoordinates(null);
    } finally {
      setLoading(false);
    }
  }

  function buildResultFromAlternative(
    alt: CompareRoutesResponse["alternatives"][number],
    data: CompareRoutesResponse
  ): PlanRouteResponse {
    return {
      route_found: alt.route_found,
      terrain: data.terrain,
      slope: [],
      hazard_score: data.hazard_score,
      route: alt.route,
      metrics: alt.metrics,
      csv_data: alt.csv_data ?? "",
      metadata: data.metadata,
      coordinates: data.coordinates,
      start: data.start,
      goal: data.goal,
    };
  }

  async function handleCompare() {
    if (!roverApiFields || (routeValidation && !routeValidation.feasible)) {
      return;
    }

    setCompareLoading(true);
    setError(null);
    setSaveMessage(null);

    try {
      const response = await compareRoutes({
        terrain_mode: controls.terrainMode,
        site_id: controls.terrainMode === "site" ? controls.siteId : undefined,
        terrain_size: controls.terrainSize,
        resolution_m_per_pixel: controls.resolution,
        ...roverApiFields,
        start,
        goal,
        hazard_weight: controls.hazardWeight,
        ...moonbaseRequestFields(moonbase),
      });
      setComparison(response);
      setCoordinates(response.coordinates);

      const bestId =
        response.best_by_metric.overall ??
        response.alternatives.find((a) => a.route_found)?.id ??
        null;
      setSelectedAlternativeId(bestId);

      const selected = response.alternatives.find((a) => a.id === bestId);
      if (selected?.route_found) {
        setResult(buildResultFromAlternative(selected, response));
      }
      scrollToResults();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Comparison failed");
      setComparison(null);
    } finally {
      setCompareLoading(false);
    }
  }

  function handleSelectAlternative(id: string) {
    if (!comparison) return;
    setSelectedAlternativeId(id);
    const selected = comparison.alternatives.find((a) => a.id === id);
    if (selected?.route_found) {
      setResult(buildResultFromAlternative(selected, comparison));
    }
  }

  function handleDemUploaded() {
    loadPreview();
  }

  async function handleSave() {
    if (!result) return;

    setSaveMessage(null);
    try {
      const response = await saveRun({
        rover_name: activeRoverConfig?.name ?? roverModeLabel(roverMode, activeRoverConfig),
        terrain_size: controls.terrainSize,
        resolution_m_per_pixel: controls.resolution,
        start_row: controls.startRow,
        start_col: controls.startCol,
        goal_row: controls.goalRow,
        goal_col: controls.goalCol,
        hazard_weight: controls.hazardWeight,
        route_found: result.route_found,
        distance_m: result.metrics.distance_m,
        estimated_time_min: result.metrics.estimated_time_min,
        max_slope_deg: result.metrics.max_slope_deg,
        average_slope_deg: result.metrics.average_slope_deg,
        average_hazard_score: result.metrics.average_hazard_score,
        energy_score: result.metrics.energy_score,
        route_json: result.route,
      });
      setSaveMessage(response.message);
    } catch (err) {
      setSaveMessage(err instanceof Error ? err.message : "Save failed");
    }
  }

  const previewGrid = preview?.terrain ?? null;
  const previewHillshade = preview?.hillshade ?? null;

  const routeOverlays = comparison
    ? comparison.alternatives
        .filter((a) => a.route_found)
        .map((a) => ({
          route: a.route,
          color: a.color,
          label: a.label,
        }))
    : undefined;

  const selectedAlternative = comparison?.alternatives.find(
    (a) => a.id === selectedAlternativeId
  );

  const hasRouteResults = !!(result?.route_found || comparison);
  const hazardGrid = result?.hazard_score ?? comparison?.hazard_score ?? null;

  useEffect(() => {
    const mq = window.matchMedia("(min-width: 901px)");
    const sync = () => setIsDesktopLayout(mq.matches);
    sync();
    mq.addEventListener("change", sync);
    return () => mq.removeEventListener("change", sync);
  }, []);

  const showControls = isDesktopLayout || mobileControlsOpen;

  const fallbackRoverConfig: RoverConfig = activeRoverConfig ?? {
    name: "Astrolab CLV-1",
    max_slope_deg: 20,
    nominal_speed_mps: 2.8,
    roughness_tolerance: 0.3,
    energy_factor: 1.18,
    max_range_m: 4000,
    description: "",
  };

  const rangeExceeded = result?.route_found && result.metrics.range_exceeded;

  return (
    <>
      {!isSupabaseConfigured() && (
        <div className="status-banner app-banner">Supabase not configured yet.</div>
      )}

      {error && <p className="error app-banner">{error}</p>}

      <div className="app-layout">
        <div className="app-layout-top">
          <StepIndicator
            hasPreview={!!preview}
            hasResult={!!result?.route_found || !!comparison}
            previewLoading={previewLoading}
          />
        </div>

        <div className="main-content">
          {(previewMetadata || coordinates || routeValidation || activeRoverConfig) && (
            <div className="info-bar">
              {previewMetadata && (
                <div className="info-bar-section">
                  <span className="info-bar-label">Site</span>
                  <strong>{previewMetadata.site_name ?? "Synthetic terrain"}</strong>
                  {previewMetadata.center_lat != null && (
                    <span className="coord-badge">
                      {previewMetadata.center_lat.toFixed(2)}°,{" "}
                      {previewMetadata.center_lon?.toFixed(2)}°
                    </span>
                  )}
                  {previewMetadata.center_note && (
                    <span className="coord-badge">{previewMetadata.center_note}</span>
                  )}
                  {previewMetadata.coverage_status === "partial" && previewMetadata.coverage_note && (
                    <span className="coord-badge">{previewMetadata.coverage_note}</span>
                  )}
                  {previewMetadata.coverage_status === "unsuitable" && previewMetadata.coverage_note && (
                    <span className="coord-badge">{previewMetadata.coverage_note}</span>
                  )}
                  {previewMetadata.terrain_kind === "synthetic" && (
                    <span className="coord-badge">Synthetic terrain, not a NASA DEM</span>
                  )}
                </div>
              )}

              {activeRoverConfig && (
                <div className="info-bar-section">
                  <span className="info-bar-label">Rover</span>
                  <strong>{roverModeLabel(roverMode, activeRoverConfig)}</strong>
                  {isRoverDirty && roverMode !== "custom" && (
                    <span className="coord-badge">customized</span>
                  )}
                </div>
              )}

              {(preview || coordinates) && (
                <div className="info-bar-section info-bar-points">
                  <div className="point-chip point-chip-a">
                    <span className="pick-dot start" aria-hidden="true" />
                    <span>
                      A · row {controls.startRow}, col {controls.startCol}
                    </span>
                  </div>
                  <span className="info-bar-arrow" aria-hidden="true">→</span>
                  <div className="point-chip point-chip-b">
                    <span className="pick-dot goal" aria-hidden="true" />
                    <span>
                      B · row {controls.goalRow}, col {controls.goalCol}
                    </span>
                  </div>
                </div>
              )}

              {routeValidation && (
                <div
                  className={`info-bar-status${
                    routeValidation.feasible ? " ok" : " error"
                  }`}
                >
                  <span aria-hidden="true">{routeValidation.feasible ? "✓" : "⚠"}</span>
                  {routeValidation.message}
                </div>
              )}
            </div>
          )}

          <div className="panel panel-accent terrain-viewer-panel">
            <TerrainViewer
              terrainGrid={previewGrid ?? (result?.terrain ?? comparison?.terrain) ?? null}
              hillshade={previewHillshade}
              hazardGrid={hazardGrid}
              illuminationGrid={preview?.illumination ?? null}
              psrGrid={preview?.psr_mask ?? null}
              commsGrid={preview?.comms_gap_mask ?? null}
              moonbase={moonbase}
              phaseInfo={
                moonbaseCatalog?.phases.find((item) => item.id === moonbase.phase) ?? null
              }
              resolutionM={previewMetadata?.resolution_m_per_pixel ?? controls.resolution}
              maxSlopeDeg={activeRoverConfig?.max_slope_deg ?? 20}
              functionalGaps={preview?.moonbase?.functional_gaps}
              route={comparison ? undefined : result?.route}
              routeOverlays={hasRouteResults ? routeOverlays : undefined}
              start={start}
              goal={goal}
              analysis={analysis}
              interactive={!previewLoading && !!previewGrid}
              pickMode={pickMode}
              onCellClick={handleCellClick}
              loading={previewLoading}
              previewError={previewError}
              hero
              showLayerTabs
              showRoutes={hasRouteResults}
              animateRoute={hasRouteResults}
              title={
                previewMetadata?.site_name
                  ? `${previewMetadata.site_name} — lunar terrain`
                  : "Lunar terrain"
              }
              subtitle={
                hasRouteResults
                  ? comparison
                    ? "Compare routes below · criteria sit on the surface · try 3D view"
                    : "Route computed · criteria sit on the surface · try 3D view"
                  : pickMode === "start"
                    ? "Click the map to place Point A (start)"
                    : "Click the map to place Point B (goal)"
              }
            />
          </div>

          {!hasRouteResults && (
            <div className="panel panel-hint" id="route-results" ref={resultsRef}>
                <div className="empty-state empty-state-compact">
                <p className="empty-state-title">No path on the map yet</p>
                <p className="empty-state-hint">
                  Place A and B, then use Plan this route for one rover or Compare rovers for both.
                </p>
              </div>
            </div>
          )}

          {hasRouteResults && <div id="route-results" ref={resultsRef} />}

          <RouteComparisonDashboard
            comparison={comparison}
            loading={compareLoading}
            selectedId={selectedAlternativeId}
            onSelect={handleSelectAlternative}
          />

          {(result?.route_found || saveMessage) && (
            <div className="panel panel-results-footer">
              <div className="panel-header">
                <div>
                  <h2>What this route costs</h2>
                  {selectedAlternative && (
                    <p className="panel-subtitle">
                      {selectedAlternative.label} · {selectedAlternative.rover_name}
                    </p>
                  )}
                </div>
                <RouteExport
                  csvData={result?.csv_data ?? null}
                  onSave={handleSave}
                  saveMessage={saveMessage}
                  disabled={!result || !result.route_found}
                  inline
                />
              </div>
              {rangeExceeded && result && (
                <div className="status-banner range-warning-banner">
                  {result.metrics.distance_m > result.metrics.max_range_m
                    ? `Route distance (${result.metrics.distance_m.toLocaleString()} m) exceeds this rover's max travel range (${result.metrics.max_range_m.toLocaleString()} m).`
                    : `After cargo and shadow, this route uses more than the rover's ${result.metrics.max_range_m.toLocaleString()} m range. Power margin is ${(result.metrics.power_margin_m ?? 0).toLocaleString()} m.`}
                </div>
              )}
              <MetricsTable
                metrics={result?.metrics ?? null}
                routeFound={result?.route_found ?? false}
                compact
              />
            </div>
          )}
        </div>

        <aside className={`sidebar${showControls ? " sidebar-open" : ""}`}>
          {!isDesktopLayout && (
            <button
              type="button"
              className="sidebar-toggle"
              onClick={() => setMobileControlsOpen((o) => !o)}
              aria-expanded={mobileControlsOpen}
            >
              {mobileControlsOpen ? "Hide controls" : "Show how to plan a route"}
            </button>
          )}
          {showControls && (
            <RouteControls
              roverMode={roverMode}
              activeRoverConfig={fallbackRoverConfig}
              astrolabPreset={astrolabPreset}
              pegasusPreset={pegasusPreset}
              presetOverrides={presetOverrides}
              customRovers={customRovers}
              selectedSavedCustomName={selectedSavedCustomName}
              isRoverDirty={isRoverDirty}
              roverSaveMessage={roverSaveMessage}
              sites={sites}
              values={controls}
              pickMode={pickMode}
              onPickModeChange={setPickMode}
              onChange={setControls}
              onRoverModeChange={handleRoverModeChange}
              onPresetConfigChange={handlePresetConfigChange}
              onResetPreset={handleResetPreset}
              onRoverConfigChange={handleRoverConfigChange}
              onLoadSavedCustom={handleLoadSavedCustom}
              onSaveCustomRover={handleSaveCustomRover}
              onDeleteCustomRover={handleDeleteCustomRover}
              onRun={handleRun}
              onCompare={handleCompare}
              loading={loading}
              compareLoading={compareLoading}
              previewLoading={previewLoading}
              runDisabled={!!routeValidation && !routeValidation.feasible}
              compareDisabled={!!routeValidation && !routeValidation.feasible}
              demUpload={
                controls.terrainMode === "site" ? (
                  <DemUpload siteId={controls.siteId} onUploaded={handleDemUploaded} />
                ) : undefined
              }
              leading={
                <MoonbaseControls
                  part="phase"
                  catalog={moonbaseCatalog}
                  settings={moonbase}
                  pickMode={pickMode}
                  onChange={handleMoonbaseChange}
                  onPickModeChange={setPickMode}
                />
              }
              beforeActions={
                <MoonbaseControls
                  part="rules"
                  catalog={moonbaseCatalog}
                  settings={moonbase}
                  pickMode={pickMode}
                  onChange={handleMoonbaseChange}
                  onPickModeChange={setPickMode}
                />
              }
            />
          )}
        </aside>
      </div>
    </>
  );
}
