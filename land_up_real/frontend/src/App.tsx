import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import FloorPlanVisualizer from './components/FloorPlanVisualizer';
import MarkerIcon, { MARKER_CONFIG } from './components/MarkerIcon';
import type { MarkerType } from './components/MarkerIcon';
import type { FinalLayoutData, UserMarking, ManualMarkingRequiredResponse, BrandConstraints } from './types';
import './index.css';

// 접기/펼치기 섹션 컴포넌트
function AccordionSection({
  title,
  defaultOpen = true,
  children,
  isDark,
}: {
  title: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
  isDark: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className={`rounded-lg border overflow-hidden ${isDark ? 'border-slate-700' : 'border-slate-200'}`}>
      <button
        onClick={() => setOpen(o => !o)}
        className={`w-full flex items-center justify-between px-3 py-2.5 text-left transition-colors ${
          isDark
            ? 'bg-slate-700/60 hover:bg-slate-700 text-slate-200'
            : 'bg-slate-100 hover:bg-slate-200 text-slate-700'
        }`}
      >
        <span className="text-base font-semibold uppercase tracking-wider">{title}</span>
        <span className={`text-base transition-transform ${open ? 'rotate-180' : ''}`}>▼</span>
      </button>
      {open && (
        <div className="p-3 space-y-2 overflow-y-auto max-h-[200px] custom-scrollbar">
          {children}
        </div>
      )}
    </div>
  );
}

function App() {
  // 테마
  const [isDark, setIsDark] = useState<boolean>(() => {
    return localStorage.getItem('theme') === 'dark';
  });

  useEffect(() => {
    if (isDark) {
      document.documentElement.classList.add('dark');
      localStorage.setItem('theme', 'dark');
    } else {
      document.documentElement.classList.remove('dark');
      localStorage.setItem('theme', 'light');
    }
  }, [isDark]);

  // 파일 / 결과 상태
  const [manual, setManual] = useState<File | null>(null);
  const [image, setImage] = useState<File | null>(null);
  const [imagePreviewUrl, setImagePreviewUrl] = useState<string | null>(null);
  const [layoutResult, setLayoutResult] = useState<FinalLayoutData | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [activeHighlightId, setActiveHighlightId] = useState<string | null>(null);

  // 수동 마킹
  const [isMarkingMode, setIsMarkingMode] = useState(false);
  const [userMarkings, setUserMarkings] = useState<UserMarking[]>([]);
  const [selectedType, setSelectedType] = useState<MarkerType>('sprinkler');
  const [tempBrandRules, setTempBrandRules] = useState<BrandConstraints | null>(null);
  const markingImgRef = useRef<HTMLImageElement>(null);

  useEffect(() => {
    if (image) {
      const url = URL.createObjectURL(image);
      setImagePreviewUrl(url);
      return () => URL.revokeObjectURL(url);
    }
  }, [image]);

  const handleManualUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.length) setManual(e.target.files[0]);
  };

  const handleImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.length) {
      setImage(e.target.files[0]);
      setUserMarkings([]);
      setIsMarkingMode(false);
    }
  };

  const onImageClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!isMarkingMode || !markingImgRef.current) return;
    const rect = markingImgRef.current.getBoundingClientRect();
    const xRatio = (e.clientX - rect.left) / rect.width;
    const yRatio = (e.clientY - rect.top) / rect.height;
    setUserMarkings([...userMarkings, { x: xRatio, y: yRatio, type: selectedType }]);
  };

  const removeMarking = (index: number) => {
    setUserMarkings(userMarkings.filter((_, i) => i !== index));
  };

  const handleSubmit = async (e?: React.FormEvent, forceMarkings: UserMarking[] | null = null) => {
    if (e) e.preventDefault();
    if (!manual || !image) {
      setErrorMsg('브랜드 룰 문서와 도면 이미지를 모두 첨부해주세요.');
      return;
    }
    setErrorMsg('');
    setIsLoading(true);
    if (!forceMarkings) setLayoutResult(null);

    const formData = new FormData();
    formData.append('brand_manual', manual);
    formData.append('floor_plan', image);
    const markingsToUse = forceMarkings || userMarkings;
    if (markingsToUse.length > 0) {
      formData.append('user_markings', JSON.stringify(markingsToUse));
    }

    try {
      const res = await axios.post<FinalLayoutData | ManualMarkingRequiredResponse>(
        'http://localhost:8000/api/generate',
        formData,
        { headers: { 'Content-Type': 'multipart/form-data' } }
      );
      if ((res.data as any).status === 'manual_marking_required') {
        const manualData = res.data as ManualMarkingRequiredResponse;
        console.warn('AI가 시설물을 찾지 못해 수동 마킹 모드로 전환합니다.');
        setIsMarkingMode(true);
        setTempBrandRules(manualData.brand);
        setErrorMsg('AI가 도면에서 시설물을 찾지 못했습니다. 도면 위를 클릭하여 위치를 직접 표시해 주세요.');
      } else {
        const successData = res.data as FinalLayoutData;
        console.log('Agent Pipeline Output:', successData);
        setLayoutResult(successData);
        setIsMarkingMode(false);
        setTempBrandRules(null);
      }
    } catch (err: any) {
      console.error(err);
      setErrorMsg(err.response?.data?.detail || 'AI 파이프라인 연산 중 에러가 발생했습니다.');
    } finally {
      setIsLoading(false);
    }
  };

  // 공통 색상 클래스
  const panelBg = isDark ? 'bg-[#1e293b] border-slate-700' : 'bg-white border-slate-200';
  const textPrimary = isDark ? 'text-slate-100' : 'text-slate-800';
  const textSecondary = isDark ? 'text-slate-400' : 'text-slate-500';
  const textLabel = isDark ? 'text-slate-300' : 'text-slate-600';
  const inputFile = isDark
    ? 'text-slate-400 file:bg-blue-900/40 file:text-blue-300 hover:file:bg-blue-900/60'
    : 'text-slate-500 file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100';

  const markerTypes: MarkerType[] = ['sprinkler', 'fire_hydrant', 'electrical_panel', 'entrance', 'pillar'];

  return (
    <div className={`flex flex-col h-screen ${isDark ? 'bg-[#0f172a]' : 'bg-slate-100'} transition-colors duration-200`}>

      {/* 헤더 */}
      <header className={`shrink-0 flex items-center justify-between px-6 py-3 border-b ${
        isDark ? 'bg-[#0f172a] border-slate-800' : 'bg-white border-slate-200'
      }`}>
        <h1 className={`text-lg font-bold tracking-tight ${isDark ? 'text-white' : 'text-slate-800'}`}>
          LandingUp <span className={isDark ? 'text-blue-400' : 'text-blue-600'}>AI</span>
        </h1>
        {/* Light / Dark 토글 */}
        <div className={`flex rounded-md overflow-hidden border text-xs font-semibold ${isDark ? 'border-slate-600' : 'border-slate-300'}`}>
          <button
            onClick={() => setIsDark(false)}
            className={`px-3 py-1.5 transition-colors ${!isDark ? 'bg-blue-500 text-white' : 'text-slate-400 hover:text-white'}`}
          >
            Light
          </button>
          <button
            onClick={() => setIsDark(true)}
            className={`px-3 py-1.5 transition-colors ${isDark ? 'bg-blue-500 text-white' : 'text-slate-600 hover:text-slate-900'}`}
          >
            Dark
          </button>
        </div>
      </header>

      {/* 메인 3분할 레이아웃 */}
      <div className="flex flex-1 overflow-hidden">

        {/* ── 왼쪽: 파일 업로드 + 마킹 ── */}
        <aside className={`w-[260px] xl:w-[300px] 2xl:w-[320px] shrink-0 flex flex-col gap-3 p-4 border-r overflow-y-auto custom-scrollbar ${panelBg} ${isDark ? 'border-slate-700' : 'border-slate-200'}`}>

          {/* 파일 업로드 */}
          <div>
            <p className={`text-sm font-semibold uppercase tracking-wider mb-2 ${textSecondary}`}>파일 업로드</p>
            <form onSubmit={(e) => handleSubmit(e)} className="space-y-3">
              <div>
                <label className={`block text-base font-medium mb-1 ${textLabel}`}>브랜드 매뉴얼 (.md, .pdf)</label>
                <input
                  type="file"
                  onChange={handleManualUpload}
                  className={`text-sm w-full file:mr-2 file:py-1.5 file:px-3 file:rounded file:border-0 file:text-sm file:font-semibold cursor-pointer ${inputFile}`}
                />
              </div>
              <div>
                <label className={`block text-base font-medium mb-1 ${textLabel}`}>도면 파일 (.png, .jpg, .pdf)</label>
                <input
                  type="file"
                  onChange={handleImageUpload}
                  className={`text-sm w-full file:mr-2 file:py-1.5 file:px-3 file:rounded file:border-0 file:text-sm file:font-semibold cursor-pointer ${inputFile}`}
                />
              </div>
              <button
                type="submit"
                disabled={isLoading}
                className={`w-full py-2 rounded text-white text-base font-bold transition-all ${
                  isLoading
                    ? 'bg-slate-500 cursor-not-allowed'
                    : 'bg-blue-600 hover:bg-blue-700 active:scale-95'
                }`}
              >
                {isLoading ? '실행 중...' : '자동 배치 실행'}
              </button>
              {errorMsg && (
                <div className={`p-2.5 text-xs rounded border font-medium ${
                  isMarkingMode
                    ? isDark ? 'bg-amber-900/30 text-amber-300 border-amber-700' : 'bg-amber-50 text-amber-700 border-amber-200'
                    : isDark ? 'bg-red-900/30 text-red-300 border-red-700' : 'bg-red-50 text-red-600 border-red-200'
                }`}>
                  {errorMsg}
                </div>
              )}
            </form>
          </div>

          {/* 시설물 수동 마킹 - 항상 표시 */}
          <div className={`rounded-lg border p-3 space-y-2 ${isDark ? 'border-slate-700' : 'border-slate-200'}`}>
            <p className={`text-base font-semibold uppercase tracking-wider ${textSecondary}`}>시설물 수동 마킹</p>
            <div className="space-y-1.5">
              {markerTypes.map(t => {
                const cfg = MARKER_CONFIG[t];
                const isSelected = selectedType === t;
                return (
                  <button
                    key={t}
                    onClick={() => setSelectedType(t)}
                    className={`w-full flex items-center gap-2.5 px-3 py-2 rounded text-sm font-medium transition-all border ${
                      isSelected
                        ? 'border-blue-500 bg-blue-600/20 text-blue-400'
                        : isDark
                          ? 'border-slate-700 text-slate-400 hover:border-slate-500'
                          : 'border-slate-200 text-slate-600 hover:border-slate-400'
                    }`}
                  >
                    <MarkerIcon type={t} size={22} color={isSelected ? '#60a5fa' : cfg.color} />
                    <span>{cfg.label}</span>
                  </button>
                );
              })}
            </div>
            <button
              onClick={() => setIsMarkingMode(o => !o)}
              disabled={!image}
              className={`w-full py-2 rounded text-sm font-bold transition-all ${
                !image
                  ? 'bg-slate-300 cursor-not-allowed text-slate-400'
                  : isMarkingMode
                    ? 'bg-amber-500 hover:bg-amber-600 text-white'
                    : isDark
                      ? 'bg-slate-600 hover:bg-slate-500 text-white border border-slate-500'
                      : 'bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-300'
              }`}
            >
              {isMarkingMode ? '✓ 마킹 완료' : '✎ 도면에 마킹하기'}
            </button>
            {userMarkings.length > 0 && (
              <div className="space-y-1.5 pt-1">
                <p className={`text-xs font-semibold uppercase tracking-wider ${textSecondary}`}>마킹 목록 ({userMarkings.length})</p>
                {userMarkings.map((m, i) => {
                  const cfg = MARKER_CONFIG[m.type as MarkerType];
                  return (
                    <div
                      key={i}
                      className={`flex items-center justify-between px-2 py-1.5 rounded border text-xs ${
                        isDark ? 'border-slate-700 bg-slate-800' : 'border-slate-200 bg-slate-50'
                      }`}
                    >
                      <div className="flex items-center gap-1.5 min-w-0">
                        <MarkerIcon type={m.type as MarkerType} size={14} color={cfg.color} />
                        <span className={`font-mono truncate ${textSecondary}`}>
                          {cfg.label} {Math.round(m.x * 100)}%,{Math.round(m.y * 100)}%
                        </span>
                      </div>
                      <button onClick={() => removeMarking(i)} className="text-red-400 hover:text-red-300 font-bold ml-1 shrink-0">×</button>
                    </div>
                  );
                })}
                <div className="flex gap-1.5">
                  <button
                    onClick={() => handleSubmit()}
                    className="flex-1 py-1.5 bg-amber-500 hover:bg-amber-600 text-white rounded text-xs font-bold"
                  >
                    재실행
                  </button>
                  <button
                    onClick={() => setUserMarkings([])}
                    className={`flex-1 py-1.5 rounded text-xs font-bold border transition-colors ${
                      isDark ? 'border-slate-600 text-slate-400 hover:border-slate-400' : 'border-slate-300 text-slate-500 hover:border-slate-500'
                    }`}
                  >
                    초기화
                  </button>
                </div>
              </div>
            )}
          </div>
        </aside>

        {/* ── 중앙: 뷰어 ── */}
        <main className="flex-1 p-3 overflow-hidden">
          <div className="w-full h-full relative">
            {isLoading ? (
              <div className={`flex w-full h-full items-center justify-center flex-col gap-3 rounded-lg ${isDark ? 'bg-[#1e293b]' : 'bg-white border border-slate-200'}`}>
                <div className="w-8 h-8 rounded-full border-4 border-slate-300 border-t-blue-500 animate-spin" />
                <span className={`text-base font-medium ${textSecondary}`}>배치 실행 중입니다...</span>
              </div>
            ) : layoutResult ? (
              <FloorPlanVisualizer
                layoutData={layoutResult}
                activeHighlightId={activeHighlightId}
                isDark={isDark}
              />
            ) : isMarkingMode && imagePreviewUrl ? (
              /* 결과 없을 때만: 전체화면 마킹 캔버스 */
              <div className={`flex flex-col w-full h-full rounded-lg overflow-hidden ${isDark ? 'bg-[#0f172a]' : 'bg-slate-800'}`}>
                <div className="px-4 py-2.5 flex items-center justify-between bg-slate-900">
                  <span className="text-white text-sm font-semibold">도면 시설물 수동 마킹</span>
                  <span className="text-slate-400 text-xs">도면 위를 클릭해 마킹하세요</span>
                </div>
                <div
                  className="flex-1 relative overflow-auto flex items-center justify-center p-4 bg-black/40 cursor-crosshair"
                  onClick={onImageClick}
                >
                  <div className="relative inline-block shadow-2xl">
                    <img ref={markingImgRef} src={imagePreviewUrl} className="max-h-[70vh] block pointer-events-none select-none" alt="Marking Target" />
                    {userMarkings.map((m, i) => {
                      const cfg = MARKER_CONFIG[m.type as MarkerType];
                      return (
                        <div key={i} className="absolute pointer-events-none" style={{ left: `${m.x * 100}%`, top: `${m.y * 100}%`, transform: 'translate(-50%, -50%)' }}>
                          <div className="flex items-center justify-center w-7 h-7 rounded-full border-2 border-white shadow-lg" style={{ backgroundColor: cfg.color }}>
                            <MarkerIcon type={m.type as MarkerType} size={14} color="white" />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            ) : (
              <div className={`flex w-full h-full items-center justify-center rounded-lg border ${
                isDark ? 'bg-[#1e293b] border-slate-700' : 'bg-white border-slate-200'
              }`}>
                <div className="text-center max-w-sm px-8">
                  <div className={`w-20 h-20 mx-auto mb-6 rounded-2xl flex items-center justify-center text-4xl ${
                    isDark ? 'bg-blue-900/30 text-blue-400' : 'bg-blue-50 text-blue-500'
                  } animate-pulse`}>
                    🗺️
                  </div>
                  <h2 className={`text-2xl font-bold mb-2 ${textPrimary}`}>팝업 배치 AI</h2>
                  <p className={`text-base mb-8 ${textSecondary}`}>
                    브랜드 룰과 도면을 분석해<br />최적의 오브젝트 배치를 자동으로 제안합니다.
                  </p>
                  <div className="space-y-2.5 text-left">
                    {[
                      { step: '01', label: '브랜드 매뉴얼 업로드', desc: '.md 또는 .pdf 파일' },
                      { step: '02', label: '도면 이미지 업로드', desc: '.png / .jpg / .pdf 파일' },
                      { step: '03', label: '자동 배치 실행', desc: 'AI가 최적 위치를 계산합니다' },
                    ].map(({ step, label, desc }) => (
                      <div key={step} className={`flex items-center gap-3 px-4 py-3 rounded-xl border transition-colors ${
                        isDark ? 'bg-slate-800/60 border-slate-700 hover:border-slate-500' : 'bg-slate-50 border-slate-200 hover:border-slate-300'
                      }`}>
                        <span className={`text-base font-extrabold w-7 shrink-0 ${isDark ? 'text-blue-400' : 'text-blue-500'}`}>{step}</span>
                        <div>
                          <div className={`text-base font-semibold ${textPrimary}`}>{label}</div>
                          <div className={`text-sm mt-0.5 ${textSecondary}`}>{desc}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* 결과 있을 때 마킹 모드: 3D도면 위에 반투명 오버레이 */}
            {isMarkingMode && imagePreviewUrl && layoutResult && (
              <div className="absolute inset-0 z-20 flex flex-col rounded-lg overflow-hidden bg-black/75">
                <div className="px-4 py-2.5 flex items-center justify-between bg-slate-900 shrink-0">
                  <span className="text-white text-sm font-semibold">시설물 수동 마킹 모드</span>
                  <span className="text-amber-300 text-xs">← 왼쪽 ✓ 마킹 완료를 누르면 3D 도면으로 돌아갑니다</span>
                </div>
                <div
                  className="flex-1 relative overflow-auto flex items-center justify-center p-4 cursor-crosshair"
                  onClick={onImageClick}
                >
                  <div className="relative inline-block shadow-2xl">
                    <img ref={markingImgRef} src={imagePreviewUrl} className="max-h-[70vh] block pointer-events-none select-none" alt="Marking Target" />
                    {userMarkings.map((m, i) => {
                      const cfg = MARKER_CONFIG[m.type as MarkerType];
                      return (
                        <div key={i} className="absolute pointer-events-none" style={{ left: `${m.x * 100}%`, top: `${m.y * 100}%`, transform: 'translate(-50%, -50%)' }}>
                          <div className="flex items-center justify-center w-7 h-7 rounded-full border-2 border-white shadow-lg" style={{ backgroundColor: cfg.color }}>
                            <MarkerIcon type={m.type as MarkerType} size={14} color="white" />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            )}
          </div>
        </main>

        {/* ── 오른쪽: 결과 패널 ── */}
        {(layoutResult || tempBrandRules) && (
          <aside className={`w-[260px] xl:w-[300px] 2xl:w-[320px] shrink-0 flex flex-col gap-3 p-4 border-l overflow-y-auto custom-scrollbar ${panelBg} ${isDark ? 'border-slate-700' : 'border-slate-200'}`}>
            <p className={`shrink-0 text-base font-semibold uppercase tracking-wider ${textSecondary}`}>배치 결과</p>

            {/* AI 추출 제약 조건 */}
            {(layoutResult?.brand_rules || tempBrandRules) && (
              <AccordionSection title="AI 추출 제약 조건" isDark={isDark}>
                {Object.entries((layoutResult?.brand_rules || tempBrandRules)!).map(([key, item]: [string, any]) => {
                  if (key === 'relationships') {
                    return (
                      <div key={key} className={`p-2.5 rounded text-xs border ${isDark ? 'bg-indigo-900/20 border-indigo-800 text-indigo-300' : 'bg-indigo-50 border-indigo-100 text-indigo-700'}`}>
                        <span className="font-bold block mb-1">관계 제약</span>
                        <ul className="list-disc pl-3 space-y-0.5">
                          {item.map((r: any, idx: number) => <li key={idx}>{r.rule}</li>)}
                        </ul>
                      </div>
                    );
                  }
                  return (
                    <div key={key} className={`p-2.5 rounded text-xs border ${isDark ? 'bg-slate-800 border-slate-700' : 'bg-slate-50 border-slate-200'}`}>
                      <span className={`font-bold block mb-0.5 ${isDark ? 'text-indigo-400' : 'text-indigo-700'}`}>
                        {key.replace('_mm', '').toUpperCase()}
                      </span>
                      <span className={`font-mono ${textPrimary}`}>
                        {item.value ? `${item.value}${key.includes('mm') ? ' mm' : ''}` : <span className="text-red-400">발견 실패</span>}
                      </span>
                      <span className={`ml-1.5 text-xs ${textSecondary}`}>({item.confidence})</span>
                    </div>
                  );
                })}
              </AccordionSection>
            )}

            {/* 데드존 */}
            {layoutResult?.facilities && layoutResult.facilities.length > 0 && (
              <AccordionSection title={`데드존 (${layoutResult.facilities.length})`} isDark={isDark}>
                {layoutResult.facilities.map((fac, i) => (
                  <div
                    key={`fac-${i}`}
                    onClick={() => setActiveHighlightId(prev => prev === fac.id ? null : fac.id)}
                  className={`p-2.5 rounded border text-sm cursor-pointer transition-colors ${
                      activeHighlightId === fac.id
                        ? isDark ? 'bg-yellow-900/30 border-yellow-500 text-yellow-300' : 'bg-yellow-50 border-yellow-400 text-yellow-700'
                        : isDark ? 'bg-slate-800 border-slate-700 hover:border-slate-500 text-slate-300' : 'bg-white border-slate-200 hover:border-slate-400 text-slate-700'
                    }`}
                  >
                    <div className="font-bold text-red-400">{fac.type.toUpperCase()}</div>
                    <div className={`font-mono mt-0.5 ${textSecondary}`}>ID: {fac.id}</div>
                    <div className={`font-mono ${textSecondary}`}>반경: {fac.alert_zone_mm}mm</div>
                  </div>
                ))}
              </AccordionSection>
            )}

            {/* 배치 오브젝트 */}
            {layoutResult?.placed_objects && layoutResult.placed_objects.length > 0 && (
              <AccordionSection title={`오브젝트 (${layoutResult.placed_objects.length})`} isDark={isDark}>
                {layoutResult.placed_objects.map((obj, i) => (
                  <div
                    key={`obj-${i}`}
                    onClick={() => setActiveHighlightId(prev => prev === obj.object_id ? null : obj.object_id)}
                    className={`p-2.5 rounded border text-sm cursor-pointer transition-colors ${
                      activeHighlightId === obj.object_id
                        ? isDark ? 'bg-yellow-900/30 border-yellow-500 text-yellow-300' : 'bg-yellow-50 border-yellow-400 text-yellow-700'
                        : isDark ? 'bg-slate-800 border-slate-700 hover:border-slate-500 text-slate-300' : 'bg-white border-slate-200 hover:border-slate-400 text-slate-700'
                    }`}
                  >
                    <div className={`font-bold ${isDark ? 'text-blue-400' : 'text-blue-600'}`}>{obj.object_id.replace(/_/g, ' ').toUpperCase()}</div>
                    <div className={`font-mono mt-0.5 ${textSecondary}`}>
                      {obj.dimensions.width}×{obj.dimensions.height}mm
                    </div>
                    <div className={`font-mono ${textSecondary}`}>
                      X: {obj.placed_coordinates.x} / Y: {obj.placed_coordinates.y}
                    </div>
                  </div>
                ))}
              </AccordionSection>
            )}

            {/* 수동 마킹 결과 */}
            {layoutResult && userMarkings.length > 0 && (
              <AccordionSection title={`수동 마킹 (${userMarkings.length})`} defaultOpen={false} isDark={isDark}>
                {userMarkings.map((m, i) => {
                  const cfg = MARKER_CONFIG[m.type as MarkerType];
                  return (
                    <div
                      key={i}
                      className={`flex items-center gap-2 p-2 rounded border text-xs ${
                        isDark ? 'bg-slate-800 border-slate-700 text-slate-300' : 'bg-white border-slate-200 text-slate-700'
                      }`}
                    >
                      <div className="flex items-center justify-center w-6 h-6 rounded-full shrink-0"
                        style={{ backgroundColor: cfg.bgColor }}>
                        <MarkerIcon type={m.type as MarkerType} size={12} color={cfg.color} />
                      </div>
                      <div>
                        <div className="font-semibold" style={{ color: cfg.color }}>{cfg.label}</div>
                        <div className={`font-mono ${textSecondary}`}>
                          X: {Math.round(m.x * 100)}% / Y: {Math.round(m.y * 100)}%
                        </div>
                      </div>
                    </div>
                  );
                })}
              </AccordionSection>
            )}
          </aside>
        )}
      </div>
    </div>
  );
}

export default App;
