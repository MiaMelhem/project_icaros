export type TerrainColorMode =
  | "elevation"
  | "hazard"
  | "hillshade"
  | "illumination"
  | "psr"
  | "comms"
  | "keepout";

export function valueToRgb(
  value: number,
  min: number,
  max: number,
  colorMode: TerrainColorMode
): [number, number, number] {
  const range = max - min || 1;
  const t = (value - min) / range;

  if (colorMode === "hazard") {
    return [Math.round(255 * t), Math.round(255 * (1 - t)), 50];
  }

  if (colorMode === "illumination" || colorMode === "hillshade") {
    return hillshadeToRgb(t);
  }

  if (colorMode === "psr") {
    return t > 0.5 ? [88, 28, 135] : [42, 46, 64];
  }

  if (colorMode === "comms") {
    return t > 0.5 ? [180, 83, 9] : [15, 118, 110];
  }

  if (colorMode === "keepout") {
    return t > 0.5 ? [185, 28, 28] : [30, 41, 59];
  }

  if (t < 0.25) {
    const s = t / 0.25;
    return [0, Math.round(100 + 155 * s), Math.round(255 - 100 * s)];
  }
  if (t < 0.5) {
    const s = (t - 0.25) / 0.25;
    return [Math.round(255 * s), 255, Math.round(155 - 155 * s)];
  }
  if (t < 0.75) {
    const s = (t - 0.5) / 0.25;
    return [255, Math.round(255 - 100 * s), 0];
  }
  const s = (t - 0.75) / 0.25;
  return [255, Math.round(155 - 155 * s), 0];
}

export function valueToColor(
  value: number,
  min: number,
  max: number,
  colorMode: TerrainColorMode
): string {
  const [r, g, b] = valueToRgb(value, min, max, colorMode);
  return `rgb(${r},${g},${b})`;
}

export function hillshadeToRgb(shade: number): [number, number, number] {
  const gray = Math.round(40 + shade * 185);
  return [gray, gray, gray];
}

export function hillshadeToColor(shade: number): string {
  const [r, g, b] = hillshadeToRgb(shade);
  return `rgb(${r},${g},${b})`;
}

export function computeValueRange(
  grid: number[][],
  colorMode: TerrainColorMode,
  nodataMask?: boolean[][] | null
): { min: number; max: number } {
  let min = Infinity;
  let max = -Infinity;

  for (let r = 0; r < grid.length; r++) {
    for (let c = 0; c < grid[0].length; c++) {
      if (nodataMask?.[r]?.[c]) continue;
      const val = grid[r][c];
      if (!Number.isFinite(val)) continue;
      if (val < min) min = val;
      if (val > max) max = val;
    }
  }

  if (!Number.isFinite(min)) {
    return colorMode === "hazard" ? { min: 0, max: 1 } : { min: 0, max: 1 };
  }

  return { min, max };
}

export function gridMinMax(grid: number[][]): { min: number; max: number } {
  let min = Infinity;
  let max = -Infinity;
  for (const row of grid) {
    for (const val of row) {
      if (!Number.isFinite(val)) continue;
      if (val < min) min = val;
      if (val > max) max = val;
    }
  }
  if (!Number.isFinite(min)) return { min: 0, max: 1 };
  return { min, max };
}
