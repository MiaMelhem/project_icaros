"use client";

import { useEffect, useRef } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import {
  TerrainColorMode,
  gridMinMax,
  hillshadeToRgb,
  valueToRgb,
} from "@/lib/terrainColors";
import { TerrainAnalysisGrids } from "@/lib/routeValidation";
import {
  MARK_COLORS,
  SHADOW_LIT_FRACTION,
  routeMarkAt,
} from "@/lib/moonbaseDisplay";

export interface RouteOverlay3D {
  route: number[][];
  color: string;
  label?: string;
}

export interface TerrainScene3DProps {
  terrainGrid: number[][];
  displayGrid: (number | boolean)[][];
  hillshade?: number[][] | null;
  colorMode: TerrainColorMode;
  route?: number[][];
  routeOverlays?: RouteOverlay3D[];
  start?: [number, number];
  goal?: [number, number];
  analysis?: TerrainAnalysisGrids | null;
  interactive?: boolean;
  onCellClick?: (row: number, col: number) => void;
  routeProgress?: number;
  size: number;
  illuminationGrid?: number[][] | null;
  psrGrid?: boolean[][] | null;
  commsGrid?: boolean[][] | null;
  keepoutGrid?: boolean[][] | null;
  resolutionM?: number;
  showLighting?: boolean;
  showPsr?: boolean;
  showComms?: boolean;
  showKeepout?: boolean;
}

export default function TerrainScene3D({
  terrainGrid,
  displayGrid,
  hillshade,
  colorMode,
  route,
  routeOverlays,
  start,
  goal,
  analysis,
  interactive = false,
  onCellClick,
  routeProgress = 1,
  size,
  illuminationGrid,
  psrGrid,
  commsGrid,
  keepoutGrid,
  resolutionM = 20,
  showLighting = false,
  showPsr = false,
  showComms = false,
  showKeepout = false,
}: TerrainScene3DProps) {
  const mountRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<{
    renderer: THREE.WebGLRenderer;
    camera: THREE.PerspectiveCamera;
    controls: OrbitControls;
    terrainMesh: THREE.Mesh;
    routeLines: THREE.Line[];
    markers: THREE.Mesh[];
    animationId: number;
  } | null>(null);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount || terrainGrid.length === 0) return;

    const rows = terrainGrid.length;
    const cols = terrainGrid[0].length;
    const elevRange = gridMinMax(terrainGrid);

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x07080f);
    const viewReach = Math.max(cols, rows) * 2.4;
    scene.fog = new THREE.Fog(0x07080f, viewReach * 0.55, viewReach);

    const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 2000);
    const span = Math.max(cols, rows);
    camera.position.set(span * 0.72, span * 0.62, span * 0.9);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(size, size);
    mount.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.maxPolarAngle = Math.PI / 2.1;
    controls.minDistance = span * 0.35;
    controls.maxDistance = span * 3.2;
    controls.target.set(0, span * 0.04, 0);

    const segX = Math.max(1, cols - 1);
    const segZ = Math.max(1, rows - 1);
    const geometry = new THREE.PlaneGeometry(cols, rows, segX, segZ);
    geometry.rotateX(-Math.PI / 2);

    const positions = geometry.attributes.position;
    const colors = new Float32Array(positions.count * 3);
    const elevScale = Math.max(cols, rows) * 0.12;
    const displayRange = gridMinMax(
      displayGrid.map((row) => row.map((value) => Number(value)))
    );

    for (let i = 0; i < positions.count; i++) {
      const x = positions.getX(i);
      const z = positions.getZ(i);
      const col = Math.min(cols - 1, Math.max(0, Math.round(x + cols / 2 - 0.5)));
      const row = Math.min(rows - 1, Math.max(0, Math.round(z + rows / 2 - 0.5)));
      const elev = terrainGrid[row]?.[col] ?? 0;
      const normalized =
        elevRange.max === elevRange.min
          ? 0
          : (elev - elevRange.min) / (elevRange.max - elevRange.min);
      positions.setY(i, normalized * elevScale);

      let rgb: [number, number, number];
      if (analysis?.nodataMask[row]?.[col]) {
        rgb = [15, 15, 20];
      } else if (
        (colorMode === "hillshade" || colorMode === "illumination") &&
        (colorMode === "illumination" ? displayGrid : hillshade)?.[row]?.[col] != null
      ) {
        const shade =
          colorMode === "illumination" ? Number(displayGrid[row][col]) : hillshade![row][col];
        rgb = hillshadeToRgb(shade);
      } else if (colorMode === "psr" || colorMode === "comms" || colorMode === "keepout") {
        rgb = valueToRgb(Number(displayGrid[row][col]), 0, 1, colorMode);
      } else {
        rgb = valueToRgb(
          Number(displayGrid[row][col]),
          displayRange.min,
          displayRange.max,
          colorMode
        );
      }
      if (colorMode === "hillshade") {
        const inPsr = !!psrGrid?.[row]?.[col];
        const lit = illuminationGrid?.[row]?.[col];
        if (showLighting && lit != null && Number(lit) < SHADOW_LIT_FRACTION && !inPsr) {
          rgb = [rgb[0] * 0.42, rgb[1] * 0.45, rgb[2] * 0.55];
        }
        if (showPsr && inPsr) {
          rgb = [
            rgb[0] * 0.45 + 88 * 0.55,
            rgb[1] * 0.45 + 28 * 0.55,
            rgb[2] * 0.45 + 135 * 0.55,
          ];
        }
        if (showComms && commsGrid?.[row]?.[col]) {
          rgb = [
            rgb[0] * 0.8 + 180 * 0.2,
            rgb[1] * 0.8 + 83 * 0.2,
            rgb[2] * 0.8 + 9 * 0.2,
          ];
        }
      }
      colors[i * 3] = rgb[0] / 255;
      colors[i * 3 + 1] = rgb[1] / 255;
      colors[i * 3 + 2] = rgb[2] / 255;
    }

    geometry.setAttribute("color", new THREE.BufferAttribute(colors, 3));
    geometry.computeVertexNormals();

    const material = new THREE.MeshStandardMaterial({
      vertexColors: true,
      roughness: 0.92,
      metalness: 0.05,
    });

    const terrainMesh = new THREE.Mesh(geometry, material);
    scene.add(terrainMesh);

    scene.add(new THREE.AmbientLight(0x8899bb, 0.55));
    const keyLight = new THREE.DirectionalLight(0xffffff, 1.1);
    keyLight.position.set(cols, rows * 1.5, cols * 0.5);
    scene.add(keyLight);
    const fillLight = new THREE.DirectionalLight(0x6366f1, 0.35);
    fillLight.position.set(-cols, rows, -cols);
    scene.add(fillLight);

    const routeLines: THREE.Line[] = [];
    const markers: THREE.Mesh[] = [];

    function cellToWorld(row: number, col: number): THREE.Vector3 {
      const elev = terrainGrid[row]?.[col] ?? 0;
      const normalized =
        elevRange.max === elevRange.min
          ? 0
          : (elev - elevRange.min) / (elevRange.max - elevRange.min);
      return new THREE.Vector3(
        col + 0.5 - cols / 2,
        normalized * elevScale + 0.08,
        row + 0.5 - rows / 2
      );
    }

    function addRouteLine(points: number[][], color: string, progress: number) {
      if (points.length < 2) return;
      const end = Math.max(2, Math.floor(points.length * progress));
      const sliced = points.slice(0, end);
      const verts = sliced.map(([row, col]) => cellToWorld(row, col));
      const geo = new THREE.BufferGeometry().setFromPoints(verts);
      const line = new THREE.Line(
        geo,
        new THREE.LineBasicMaterial({ color: new THREE.Color(color) })
      );
      scene.add(line);
      routeLines.push(line);

      if (colorMode !== "hillshade") return;
      const markPositions: THREE.Vector3[] = [];
      const markColors: number[] = [];
      for (let i = 1; i < sliced.length; i++) {
        const mark = routeMarkAt(sliced[i][0], sliced[i][1], {
          lighting: showLighting,
          psr: showPsr,
          comms: showComms,
          keepout: showKeepout,
        }, {
          illumination: illuminationGrid,
          psr: psrGrid,
          comms: commsGrid,
          keepout: keepoutGrid,
          resolutionM,
        });
        if (!mark) continue;
        const a = cellToWorld(sliced[i - 1][0], sliced[i - 1][1]);
        const b = cellToWorld(sliced[i][0], sliced[i][1]);
        a.y += 0.08;
        b.y += 0.08;
        markPositions.push(a, b);
        const tint = new THREE.Color(MARK_COLORS[mark]);
        markColors.push(tint.r, tint.g, tint.b, tint.r, tint.g, tint.b);
      }
      if (markPositions.length < 2) return;
      const markGeo = new THREE.BufferGeometry().setFromPoints(markPositions);
      markGeo.setAttribute("color", new THREE.Float32BufferAttribute(markColors, 3));
      const marks = new THREE.LineSegments(
        markGeo,
        new THREE.LineBasicMaterial({ vertexColors: true })
      );
      scene.add(marks);
      routeLines.push(marks);
    }

    if (start) {
      const m = new THREE.Mesh(
        new THREE.SphereGeometry(Math.max(0.7, span * 0.012), 16, 16),
        new THREE.MeshStandardMaterial({ color: 0x22c55e, emissive: 0x114422 })
      );
      m.position.copy(cellToWorld(start[0], start[1]));
      scene.add(m);
      markers.push(m);
    }
    if (goal) {
      const m = new THREE.Mesh(
        new THREE.SphereGeometry(Math.max(0.7, span * 0.012), 16, 16),
        new THREE.MeshStandardMaterial({ color: 0xef4444, emissive: 0x441111 })
      );
      m.position.copy(cellToWorld(goal[0], goal[1]));
      scene.add(m);
      markers.push(m);
    }

    if (routeOverlays?.length) {
      for (const overlay of routeOverlays) {
        if (overlay.route?.length > 1) {
          addRouteLine(overlay.route, overlay.color, routeProgress);
        }
      }
    } else if (route && route.length > 1) {
      addRouteLine(route, "#00ffff", routeProgress);
    }

    const raycaster = new THREE.Raycaster();
    const pointer = new THREE.Vector2();

    function onClick(event: MouseEvent) {
      if (!interactive || !onCellClick) return;
      const rect = renderer.domElement.getBoundingClientRect();
      pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
      pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
      raycaster.setFromCamera(pointer, camera);
      const hits = raycaster.intersectObject(terrainMesh);
      if (hits.length === 0) return;
      const point = hits[0].point;
      const col = Math.min(cols - 1, Math.max(0, Math.round(point.x + cols / 2 - 0.5)));
      const row = Math.min(rows - 1, Math.max(0, Math.round(point.z + rows / 2 - 0.5)));
      if (row >= 0 && row < rows && col >= 0 && col < cols) {
        onCellClick(row, col);
      }
    }

    renderer.domElement.addEventListener("click", onClick);

    let animationId = 0;
    function animate() {
      animationId = requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    }
    animate();

    sceneRef.current = {
      renderer,
      camera,
      controls,
      terrainMesh,
      routeLines,
      markers,
      animationId,
    };

    return () => {
      cancelAnimationFrame(animationId);
      renderer.domElement.removeEventListener("click", onClick);
      controls.dispose();
      geometry.dispose();
      material.dispose();
      routeLines.forEach((l) => {
        l.geometry.dispose();
        (l.material as THREE.Material).dispose();
      });
      markers.forEach((m) => {
        m.geometry.dispose();
        (m.material as THREE.Material).dispose();
      });
      renderer.dispose();
      if (mount.contains(renderer.domElement)) {
        mount.removeChild(renderer.domElement);
      }
      sceneRef.current = null;
    };
  }, [
    terrainGrid,
    displayGrid,
    hillshade,
    colorMode,
    analysis,
    interactive,
    onCellClick,
    size,
    route,
    routeOverlays,
    routeProgress,
    start,
    goal,
    illuminationGrid,
    psrGrid,
    commsGrid,
    keepoutGrid,
    resolutionM,
    showLighting,
    showPsr,
    showComms,
    showKeepout,
  ]);

  useEffect(() => {
    const ctx = sceneRef.current;
    if (!ctx) return;
    ctx.renderer.setSize(size, size);
    ctx.camera.aspect = 1;
    ctx.camera.updateProjectionMatrix();
  }, [size]);

  return (
    <div
      ref={mountRef}
      className="terrain-scene-3d"
      style={{ width: size, height: size, maxWidth: "100%" }}
    />
  );
}
