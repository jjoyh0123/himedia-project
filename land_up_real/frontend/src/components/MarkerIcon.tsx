import React from 'react';

export type MarkerType = 'sprinkler' | 'fire_hydrant' | 'electrical_panel' | 'entrance' | 'pillar';

interface MarkerIconProps {
  type: MarkerType;
  size?: number;
  color?: string;
}

// 스프링클러: 원 + 방사형 선 4개 (실제 도면 심볼)
function SprinklerIcon({ size, color }: { size: number; color: string }) {
  const r = size / 2;
  const cr = r * 0.35;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} fill="none">
      <circle cx={r} cy={r} r={cr} stroke={color} strokeWidth={size * 0.1} fill="none" />
      <line x1={r} y1={r - cr} x2={r} y2={size * 0.05} stroke={color} strokeWidth={size * 0.09} strokeLinecap="round" />
      <line x1={r} y1={r + cr} x2={r} y2={size * 0.95} stroke={color} strokeWidth={size * 0.09} strokeLinecap="round" />
      <line x1={r - cr} y1={r} x2={size * 0.05} y2={r} stroke={color} strokeWidth={size * 0.09} strokeLinecap="round" />
      <line x1={r + cr} y1={r} x2={size * 0.95} y2={r} stroke={color} strokeWidth={size * 0.09} strokeLinecap="round" />
    </svg>
  );
}

// 소화전: 원 안에 H
function FireHydrantIcon({ size, color }: { size: number; color: string }) {
  const r = size / 2;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} fill="none">
      <circle cx={r} cy={r} r={r * 0.88} stroke={color} strokeWidth={size * 0.1} fill="none" />
      <text
        x={r}
        y={r + size * 0.13}
        textAnchor="middle"
        fontSize={size * 0.55}
        fontWeight="bold"
        fontFamily="monospace"
        fill={color}
      >H</text>
    </svg>
  );
}

// 전기 패널: 사각형 안에 번개
function ElectricalPanelIcon({ size, color }: { size: number; color: string }) {
  const pad = size * 0.1;
  const w = size - pad * 2;
  const h = size - pad * 2;
  const cx = size / 2;
  // 번개 모양 path
  const boltPoints = `${cx},${pad * 1.2} ${cx - w * 0.18},${size / 2} ${cx + w * 0.06},${size / 2} ${cx - w * 0.06},${size - pad * 1.2} ${cx + w * 0.18},${size / 2} ${cx - w * 0.06},${size / 2}`;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} fill="none">
      <rect x={pad} y={pad} width={w} height={h} stroke={color} strokeWidth={size * 0.1} rx={size * 0.08} fill="none" />
      <polyline points={boltPoints} stroke={color} strokeWidth={size * 0.09} strokeLinejoin="round" fill="none" />
    </svg>
  );
}

// 출입구: 벽선 + 호(문 열림 궤적)
function EntranceIcon({ size, color }: { size: number; color: string }) {
  const r = size / 2;
  const wallThick = size * 0.1;
  const doorLen = size * 0.65;
  // 왼쪽 벽, 오른쪽 벽, 문 호
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} fill="none">
      {/* 상단 벽 */}
      <line x1={0} y1={size * 0.25} x2={size * 0.22} y2={size * 0.25} stroke={color} strokeWidth={wallThick} strokeLinecap="round" />
      <line x1={size * 0.78} y1={size * 0.25} x2={size} y2={size * 0.25} stroke={color} strokeWidth={wallThick} strokeLinecap="round" />
      {/* 문 (닫힌 선) */}
      <line x1={size * 0.22} y1={size * 0.25} x2={size * 0.22} y2={size * 0.88} stroke={color} strokeWidth={size * 0.09} strokeLinecap="round" />
      {/* 호 (문 열림 궤적) */}
      <path
        d={`M ${size * 0.22} ${size * 0.25} A ${doorLen} ${doorLen} 0 0 1 ${size * 0.78} ${size * 0.25}`}
        stroke={color}
        strokeWidth={size * 0.08}
        strokeDasharray={`${size * 0.12} ${size * 0.08}`}
        fill="none"
      />
    </svg>
  );
}

// 기둥: 속이 꽉 찬 사각형 (단면)
function PillarIcon({ size, color }: { size: number; color: string }) {
  const pad = size * 0.18;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} fill="none">
      <rect x={pad} y={pad} width={size - pad * 2} height={size - pad * 2} fill={color} stroke={color} strokeWidth={size * 0.06} rx={size * 0.04} />
    </svg>
  );
}

export default function MarkerIcon({ type, size = 20, color = 'currentColor' }: MarkerIconProps) {
  switch (type) {
    case 'sprinkler':       return <SprinklerIcon size={size} color={color} />;
    case 'fire_hydrant':    return <FireHydrantIcon size={size} color={color} />;
    case 'electrical_panel':return <ElectricalPanelIcon size={size} color={color} />;
    case 'entrance':        return <EntranceIcon size={size} color={color} />;
    case 'pillar':          return <PillarIcon size={size} color={color} />;
    default:                return null;
  }
}

export const MARKER_CONFIG: Record<MarkerType, { label: string; color: string; bgColor: string }> = {
  sprinkler:        { label: '스프링클러', color: '#ef4444', bgColor: '#fee2e2' },
  fire_hydrant:     { label: '소화전',     color: '#f97316', bgColor: '#ffedd5' },
  electrical_panel: { label: '전기 패널', color: '#eab308', bgColor: '#fef9c3' },
  entrance:         { label: '출입구',     color: '#3b82f6', bgColor: '#dbeafe' },
  pillar:           { label: '기둥',       color: '#6b7280', bgColor: '#f3f4f6' },
};
