import React, { useState, useEffect, useRef } from 'react';
import { Canvas, useThree } from '@react-three/fiber';
import { OrbitControls, Text, Line, OrthographicCamera, PerspectiveCamera } from '@react-three/drei';
import * as THREE from 'three';
import type { FinalLayoutData } from '../types';

interface VisualizerProps {
  layoutData: FinalLayoutData;
  activeHighlightId?: string | null;
  isDark?: boolean;
}

const SCALE = 0.001;
const HIGHLIGHT_COLOR = '#FFE000';

// 라이트/다크 색상 팔레트
const COLORS = {
  light: {
    canvasBg: '#e8ecf0',
    floor: '#ffffff',
    gridMain: '#c0ccd8',
    gridSub: '#dde4ec',
    object: '#5b8af0',
    deadzone: '#ef4444',
    pathway: '#059669',
    label: '#1e293b',
  },
  dark: {
    canvasBg: '#1e293b',
    floor: '#c8d4dd',
    gridMain: '#8fa8bc',
    gridSub: '#c8d4dd',
    object: '#7eb8f7',
    deadzone: '#ff6b6b',
    pathway: '#34d399',
    label: '#1e293b',
  },
};

function AdaptiveCameraZoom({ floorW, floorH }: { floorW: number; floorH: number }) {
  const { size, camera } = useThree();
  useEffect(() => {
    if (floorW <= 0 || floorH <= 0) return;
    const zoomX = size.width  / (floorW * 1.3);
    const zoomY = size.height / (floorH * 1.3);
    camera.zoom = Math.min(zoomX, zoomY);
    camera.updateProjectionMatrix();
  }, [size, floorW, floorH, camera]);
  return null;
}

function UIZoomController({ zoomDelta, setZoomDelta }: { zoomDelta: number; setZoomDelta: (v: number) => void }) {
  const { camera } = useThree();
  useEffect(() => {
    if (zoomDelta !== 0) {
      if ((camera as any).isOrthographicCamera) {
        // 2D: 20% 비율 확대/축소
        camera.zoom = Math.max(5, camera.zoom * (zoomDelta > 0 ? 1.2 : 0.833));
      } else {
        // 3D: 현재 거리의 20% 비율로 이동
        const origin = new THREE.Vector3(0, 0, 0);
        const distVec = camera.position.clone().sub(origin);
        const scaleFactor = zoomDelta > 0 ? 0.8 : 1.2;
        camera.position.copy(origin.clone().add(distVec.multiplyScalar(scaleFactor)));
      }
      camera.updateProjectionMatrix();
      setZoomDelta(0);
    }
  }, [zoomDelta, camera, setZoomDelta]);
  return null;
}

function ViewModeController({ viewMode }: { viewMode: '3D' | '2D' }) {
  const { camera } = useThree();
  const controls = useThree((state) => state.controls) as any;

  useEffect(() => {
    if (viewMode === '2D') {
      camera.position.set(0, 20, 0);
      if (controls) {
        controls.target.set(0, 0, 0);
        controls.update();
      }
      camera.lookAt(0, 0, 0);
    } else {
      camera.position.set(0, 10, 15);
      if (controls) {
        controls.target.set(0, 0, 0);
        controls.update();
      }
    }
  }, [viewMode, camera, controls]);
  return null;
}

export default function FloorPlanVisualizer({ layoutData, activeHighlightId, isDark = false }: VisualizerProps) {
  const [viewMode, setViewMode] = useState<'3D' | '2D'>('2D');
  const [zoomDelta, setZoomDelta] = useState(0);
  const captureRef = React.useRef<(() => void) | null>(null);

  // 저장 버튼 클릭 시 canvas 스냅샷 저장
  function ScreenshotHelper() {
    const { gl, scene, camera } = useThree();
    captureRef.current = () => {
      if (!window.confirm('landup_배치도.png 파일을 저장하시겠습니까?')) return;
      gl.render(scene, camera);
      const dataURL = gl.domElement.toDataURL('image/png');
      const link = document.createElement('a');
      link.href = dataURL;
      link.download = 'landup_배치도.png';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    };
    return null;
  }

  const C = isDark ? COLORS.dark : COLORS.light;

  const dims = layoutData.dimensions_mm || { width: 20000, height: 15000 };
  const floorW = dims.width * SCALE;
  const floorH = dims.height * SCALE;

  const _verts = layoutData.outline_vertices ?? [];
  const minX = _verts.length ? Math.min(..._verts.map(v => v.x)) : 0;
  const minY = _verts.length ? Math.min(..._verts.map(v => v.y)) : 0;

  const toCenter = (x: number, y: number) => [
    ((x - minX) * SCALE) - (floorW / 2),
    -(((y - minY) * SCALE) - (floorH / 2)),
  ];

  const getObjectColor = (id: string, isActive: boolean) => {
    if (isActive) return HIGHLIGHT_COLOR;
    const lower = id.toLowerCase();
    if (lower.includes('hello_kitty')) return isDark ? '#f9a8d4' : '#F472B6';
    if (lower.includes('cashier')) return isDark ? '#94a3b8' : '#64748b';
    if (lower.includes('photo')) return isDark ? '#c4b5fd' : '#A78BFA';
    return C.object;
  };

  // 2D 모드: OrbitControls 설정 - 회전 차단, 좌클릭=팬
  const orbitProps2D = {
    enableRotate: false,
    enablePan: true,
    enableZoom: true,
    mouseButtons: {
      LEFT: THREE.MOUSE.PAN,
      MIDDLE: THREE.MOUSE.DOLLY,
      RIGHT: THREE.MOUSE.PAN,
    },
  };

  // 3D 모드: 기본 OrbitControls
  const orbitProps3D = {
    enableRotate: true,
    enablePan: true,
    enableZoom: true,
    mouseButtons: {
      LEFT: THREE.MOUSE.ROTATE,
      MIDDLE: THREE.MOUSE.DOLLY,
      RIGHT: THREE.MOUSE.PAN,
    },
  };

  const orbitProps = viewMode === '2D' ? orbitProps2D : orbitProps3D;

  return (
    <div
      className="w-full h-full relative rounded-lg overflow-hidden"
      style={{ backgroundColor: C.canvasBg }}
    >
      {/* 2D/3D 토글 버튼 */}
      <div className="absolute top-3 left-3 z-10 flex">
        <div className="flex bg-white/10 backdrop-blur-sm rounded-md border border-white/20 overflow-hidden shadow">
          <button
            onClick={() => setViewMode('2D')}
            className={`px-4 py-2 text-sm font-bold transition-all ${
              viewMode === '2D'
                ? 'bg-blue-600 text-white'
                : isDark ? 'text-slate-400 hover:text-white' : 'text-slate-500 hover:text-slate-800'
            }`}
          >
            2D
          </button>
          <button
            onClick={() => setViewMode('3D')}
            className={`px-4 py-2 text-sm font-bold transition-all ${
              viewMode === '3D'
                ? 'bg-blue-600 text-white'
                : isDark ? 'text-slate-400 hover:text-white' : 'text-slate-500 hover:text-slate-800'
            }`}
          >
            3D
          </button>
        </div>
      </div>

      {/* +/- 줌 버튼 + 저장 버튼 */}
      <div className="absolute top-3 right-3 z-10 flex flex-col gap-1">
        <button
          onClick={() => setZoomDelta(1)}
          title="확대"
          className="w-9 h-9 rounded-lg bg-white/15 backdrop-blur-sm border border-white/25 text-white text-xl font-bold flex items-center justify-center hover:bg-white/30 active:scale-95 transition-all shadow"
        >+</button>
        <button
          onClick={() => setZoomDelta(-1)}
          title="축소"
          className="w-9 h-9 rounded-lg bg-white/15 backdrop-blur-sm border border-white/25 text-white text-xl font-bold flex items-center justify-center hover:bg-white/30 active:scale-95 transition-all shadow"
        >−</button>
        <button
          onClick={() => captureRef.current?.()}
          title="배치도 저장"
          className="w-9 h-9 mt-1 rounded-lg bg-emerald-500/80 backdrop-blur-sm border border-emerald-400/50 text-white text-base flex items-center justify-center hover:bg-emerald-500 active:scale-95 transition-all shadow"
        >💾</button>
      </div>

      {/* 조작 안내 - 우측 하단 */}
      <div className={`absolute bottom-3 right-3 z-10 text-xs font-mono px-2 py-1 rounded ${isDark ? 'text-slate-500 bg-black/30' : 'text-slate-400 bg-white/50'}`}>
        {viewMode === '2D'
          ? '드래그: 이동  |  휠: 확대/축소'
          : '좌클릭: 회전  |  우클릭: 이동  |  휠: 확대/축소'}
      </div>

      <Canvas shadows gl={{ preserveDrawingBuffer: true }}>
        {viewMode === '3D' ? (
          <PerspectiveCamera makeDefault position={[0, 10, 15]} fov={50} />
        ) : (
          <OrthographicCamera
            makeDefault
            position={[0, 20, 0]}
            zoom={50}
            up={[0, 0, -1]}
            near={-100}
            far={100}
          />
        )}

        <ambientLight intensity={isDark ? 1.6 : 1.0} />
        <pointLight position={[10, 20, 10]} intensity={isDark ? 2.2 : 1.5} castShadow />

        <OrbitControls
          makeDefault
          enableDamping
          dampingFactor={0.1}
          {...orbitProps}
        />
        <ViewModeController viewMode={viewMode} />
        <UIZoomController zoomDelta={zoomDelta} setZoomDelta={setZoomDelta} />
        <ScreenshotHelper />
        {viewMode === '2D' && <AdaptiveCameraZoom floorW={floorW} floorH={floorH} />}

        {/* 1. 바닥면 */}
        {(() => {
          const floorShape = new THREE.Shape();
          const pDefault = [
            { x: 0, y: 0 }, { x: dims.width, y: 0 },
            { x: dims.width, y: dims.height }, { x: 0, y: dims.height },
          ];
          const pts = layoutData.outline_vertices?.length
            ? layoutData.outline_vertices
            : layoutData.usable_ranges?.[0]?.polygon_bounds || pDefault;

          pts.forEach((pt, idx) => {
            const [cx, cy] = toCenter(pt.x, pt.y);
            if (idx === 0) floorShape.moveTo(cx, cy);
            else floorShape.lineTo(cx, cy);
          });

             return (
            <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
              <shapeGeometry args={[floorShape]} />
              <meshStandardMaterial color={C.floor} side={THREE.DoubleSide} roughness={0.75} metalness={0.1} />
            </mesh>
          );
        })()}

        {/* 그리드 */}
        <gridHelper
          args={[Math.max(floorW, floorH) * 1.5, 20, C.gridMain, C.gridSub]}
          position={[0, 0.005, 0]}
        />

        {/* 2. 가용 구역 */}
        {layoutData.usable_ranges?.map((range, i) => {
          const shape = new THREE.Shape();
          range.polygon_bounds.forEach((pt, idx) => {
            const [cx, cy] = toCenter(pt.x, pt.y);
            if (idx === 0) shape.moveTo(cx, cy);
            else shape.lineTo(cx, cy);
          });
          return (
            <mesh key={`usable-${i}`} rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.01, 0]}>
              <shapeGeometry args={[shape]} />
              <meshBasicMaterial color={C.object} opacity={0.08} transparent side={THREE.DoubleSide} />
            </mesh>
          );
        })}

        {/* 3. 시설물 데드존 */}
        {layoutData.facilities?.map((fac, i) => {
          const [cx, cy] = toCenter(fac.position.x, fac.position.y);
          const r = fac.alert_zone_mm * SCALE;
          const isAct = activeHighlightId === fac.id;
          const dzColor = isAct ? HIGHLIGHT_COLOR : C.deadzone;
          return (
            <group key={`fac-${i}`} position={[cx, 0, cy]}>
              <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.015, 0]}>
                <circleGeometry args={[r, 32]} />
                <meshBasicMaterial color={dzColor} opacity={isAct ? 0.55 : 0.22} transparent />
              </mesh>
              {viewMode === '3D' && (
                <mesh position={[0, 1.5, 0]}>
                  <cylinderGeometry args={[0.1, 0.1, 3, 8]} />
                  <meshStandardMaterial color={dzColor} emissive={dzColor} emissiveIntensity={isAct ? 1 : 0.2} />
                </mesh>
              )}
              <Text
                rotation={[-Math.PI / 2, 0, 0]}
                position={[0, 0.05, r + 0.3]}
                fontSize={0.2}
                color={isAct ? HIGHLIGHT_COLOR : C.deadzone}
              >
                {fac.type.toUpperCase()}
              </Text>
            </group>
          );
        })}

        {/* 4. 배치된 오브젝트 */}
        {layoutData.placed_objects.map((obj, i) => {
          const [cx, cy] = toCenter(obj.placed_coordinates.x, obj.placed_coordinates.y);
          const ow = obj.dimensions.width * SCALE;
          const oh = obj.dimensions.height * SCALE;
          const isAct = activeHighlightId === obj.object_id;
          const objColor = getObjectColor(obj.object_id, isAct);
          const boxH = viewMode === '2D' ? 0.02 : 1;
          return (
            <group key={`obj-${i}`} position={[cx, boxH / 2, cy]}>
              <mesh castShadow receiveShadow>
                <boxGeometry args={[ow, boxH, oh]} />
                <meshStandardMaterial
                  color={objColor}
                  emissive={isAct ? HIGHLIGHT_COLOR : objColor}
                  emissiveIntensity={isAct ? 0.6 : 0.05}
                />
              </mesh>
              <Text
                rotation={[-Math.PI / 2, 0, 0]}
                position={[0, boxH / 2 + 0.01, 0]}
                fontSize={0.16}
                color={isAct ? '#1a1a1a' : C.label}
                maxWidth={ow}
                textAlign="center"
              >
                {obj.object_id.replace(/_/g, ' ')}
              </Text>
            </group>
          );
        })}

        {/* 5. 동선 */}
        {layoutData.visitor_pathways.map((path, i) => {
          const points = path.nodes.map(n => {
            const [cx, cy] = toCenter(n.x, n.y);
            return [cx, 0.05, cy] as [number, number, number];
          });
          return points.length > 1 && (
            <Line key={`path-${i}`} points={points} color={C.pathway} lineWidth={3} dashed />
          );
        })}
      </Canvas>
    </div>
  );
}
