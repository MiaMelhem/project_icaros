/**
 * Client-side route feasibility helpers for hover tooltips.
 */

export interface TerrainAnalysisGrids {
  slope: number[][];
  blockedMask: boolean[][];
  nodataMask: boolean[][];
  maxSlopeDeg: number;
}

export interface CellHoverInfo {
  row: number;
  col: number;
  elevationM: number | null;
  slopeDeg: number | null;
  passable: boolean;
  message: string;
  reachableFromStart?: boolean;
}

function directions8(): [number, number][] {
  return [
    [-1, 0],
    [1, 0],
    [0, -1],
    [0, 1],
    [-1, -1],
    [-1, 1],
    [1, -1],
    [1, 1],
  ];
}

export function floodReachable(
  blockedMask: boolean[][],
  start: [number, number]
): Set<string> {
  const rows = blockedMask.length;
  const cols = blockedMask[0]?.length ?? 0;
  const [startRow, startCol] = start;
  const key = (r: number, c: number) => `${r},${c}`;

  if (
    startRow < 0 ||
    startRow >= rows ||
    startCol < 0 ||
    startCol >= cols ||
    blockedMask[startRow][startCol]
  ) {
    return new Set();
  }

  const visited = new Set<string>();
  const queue: [number, number][] = [[startRow, startCol]];
  visited.add(key(startRow, startCol));

  while (queue.length > 0) {
    const [row, col] = queue.shift()!;
    for (const [dRow, dCol] of directions8()) {
      const nr = row + dRow;
      const nc = col + dCol;
      const k = key(nr, nc);
      if (
        nr >= 0 &&
        nr < rows &&
        nc >= 0 &&
        nc < cols &&
        !blockedMask[nr][nc] &&
        !visited.has(k)
      ) {
        visited.add(k);
        queue.push([nr, nc]);
      }
    }
  }

  return visited;
}

export function describeHoverCell(
  row: number,
  col: number,
  terrain: number[][],
  analysis: TerrainAnalysisGrids,
  start?: [number, number]
): CellHoverInfo {
  const { slope, blockedMask, nodataMask, maxSlopeDeg } = analysis;

  if (nodataMask[row]?.[col]) {
    return {
      row,
      col,
      elevationM: null,
      slopeDeg: null,
      passable: false,
      message: "No DEM data — pick a point on mapped terrain.",
    };
  }

  const elevationM = Math.round(terrain[row][col] * 10) / 10;
  const slopeDeg = Math.round(slope[row][col] * 10) / 10;
  const passable = !blockedMask[row][col];

  if (!passable) {
    return {
      row,
      col,
      elevationM,
      slopeDeg,
      passable: false,
      message: `Too steep (${slopeDeg}° > ${maxSlopeDeg}° rover limit).`,
    };
  }

  let message = `Passable · ${elevationM} m elev · ${slopeDeg}° slope`;
  let reachableFromStart: boolean | undefined;

  if (start) {
    const reachable = floodReachable(blockedMask, start);
    reachableFromStart = reachable.has(`${row},${col}`);
    if (!reachableFromStart) {
      message += " · Not reachable from Point A";
    } else if (pickMatches(start, row, col)) {
      message = `Point A · ${elevationM} m · ${slopeDeg}° slope`;
    }
  }

  return {
    row,
    col,
    elevationM,
    slopeDeg,
    passable,
    message,
    reachableFromStart,
  };
}

function pickMatches(point: [number, number], row: number, col: number): boolean {
  return point[0] === row && point[1] === col;
}

export function validateRouteClient(
  start: [number, number],
  goal: [number, number],
  terrain: number[][],
  analysis: TerrainAnalysisGrids,
  options?: { maxRangeM?: number; resolutionM?: number }
): { feasible: boolean; message: string; reasonCode: string } {
  const startCell = describeHoverCell(start[0], start[1], terrain, analysis);
  const goalCell = describeHoverCell(goal[0], goal[1], terrain, analysis);

  if (!startCell.passable) {
    return {
      feasible: false,
      reasonCode: "start_blocked",
      message: `Point A cannot be used: ${startCell.message}`,
    };
  }

  if (!goalCell.passable) {
    return {
      feasible: false,
      reasonCode: "goal_blocked",
      message: `Point B cannot be used: ${goalCell.message}`,
    };
  }

  const reachable = floodReachable(analysis.blockedMask, start);
  if (!reachable.has(`${goal[0]},${goal[1]}`)) {
    return {
      feasible: false,
      reasonCode: "disconnected",
      message:
        "No passable path between Point A and Point B — impassable terrain or missing DEM data blocks the way. Pick both points on the same connected terrain.",
    };
  }

  let message = "Route looks feasible — run optimization to compute the path.";
  const maxRangeM = options?.maxRangeM;
  const resolutionM = options?.resolutionM;
  if (maxRangeM !== undefined && resolutionM !== undefined) {
    const rowDiff = goal[0] - start[0];
    const colDiff = goal[1] - start[1];
    const straightLineM = Math.sqrt(rowDiff ** 2 + colDiff ** 2) * resolutionM;
    if (straightLineM > maxRangeM) {
      message +=
        " Straight-line distance exceeds rover range — the optimized route may also exceed it.";
    }
  }

  return {
    feasible: true,
    reasonCode: "ok",
    message,
  };
}
