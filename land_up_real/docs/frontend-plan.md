# [목표] 프론트엔드 (React + Three.js) 시각화 도구 스캐폴딩 및 테스트

지금까지 파이썬 파이프라인(Agent 1~3)이 완벽하게 백엔드에서 작동하여 "오브젝트 크기, x/y 좌표, 회전 및 동선 노드"가 담긴 정밀한 단위의 JSON 파일이 도출되었습니다. 
이제 `landing-up.md` 원본 기획서 명세에 근거하여, 이를 눈으로 확인할 수 있는 **React Web 기반의 3D/2D Canvas 프론트엔드 앱**을 구축해 시각적 테스트(Visual Testing)를 진행합니다.

---

> [!IMPORTANT]
> **사용자 리뷰 요청 (의사결정 필요)**
> 기획서에 명시된 기술 스택인 `React + TypeScript + Three.js` 가이드를 따를 예정입니다.
> 현재 파이썬 로직들이 프로젝트 루트(`c:\...\landing-up-demo`)에 존재하므로, 소스코드 혼선을 막기 위해 프론트엔드는 **`frontend/`** 라는 하위 폴더를 새로 만들어 분리 구성하는 것이 좋겠습니다. 동의하시나요?

---

## 🛠️ 제안하는 구축 계획 (Proposed Changes)

### 1단계: 프론트엔드 프로젝트 스캐폴딩
`Vite` 기반의 가볍고 빠른 React + TS 환경을 `frontend/` 디렉토리에 구축합니다.
- 패키지 매니저: `npm` 
- 기본 템플릿: `React + TypeScript`

### 2단계: 핵심 렌더링 라이브러리 설치
3D 캔버스 및 화면 구성을 위한 라이브러리 세팅:
- `@react-three/fiber` : Three.js의 React 래퍼 (안정적인 3D 렌더링)
- `@react-three/drei` : 카메라 컨트롤(OrbitControls), 텍스트, 그림자 등 편리한 Three.js 헬퍼 라이브러리
- `tailwindcss` (선택적): UI 레이아웃 및 툴바 토글용 스타일링

### 3단계: JSON 데이터 렌더링 모듈 작성(Visualizer)

#### [NEW] `frontend/src/components/FloorPlanVisualizer.tsx`
파이썬 백엔드에서 출력한 `Agent 3`의 최종 JSON 파일을 불러와 다음 요소들을 Three.js 캔버스에 그립니다.
1. **바닥면 (Usable Ranges)**: 12m x 9m 규격의 회색계열 평면 (바닥 메쉬 처리)
2. **배치된 조형물 (Placed Objects)**:
   - JSON의 `dimensions` (width, height) 속성을 BoxGeometry 높이/너비로 환산.
   - `placed_coordinates` 속성을 3D 좌표계(x, z) 위치로 매핑하여 블록(Mesh) 배치.
   - 브랜드/종류별 컬러 코딩 (예: 헬로키티 메인 동상 = 핑크색 큐브, 캐셔 = 파란색 큐브)
3. **관람객 동선 (Visitor Pathways)**:
   - 각 `nodes` 배열 좌표를 선(Line) 개체로 이어 출입구부터 오브젝트로 이어지는 발자국(동선) 표시

### 4단계: 테스트 구동 (Local HTTP Server)
- 실제 파이프라인을 돌려 튀어나온 JSON 결과물을 `frontend/public/mock-layout.json`에 임시 정적 저장합니다.
- `npm run dev` 를 통해 로컬 웹 서버를 열고, 브라우저에서 최종 2D/3D 레이아웃을 마우스 돌려가며 육안 검증합니다.

---

## ❓ 개방형 질문 (Open Questions)
> [!NOTE]
> 1. 프론트엔드 코드를 `frontend/` 폴더 하위에 두는 것에 동의하시나요?
> 2. 초기 기획에 언급된 Tailwind CSS 를 포함해 기초 UI 레이아웃 세팅을 같이 해드릴까요? (단순히 화면 정중앙에 캔버스만 꽉 채우는 형태를 원하시나요?)

---

## 🔍 검증 계획 (Verification Plan)
- **명령어**: 터미널에서 `npm run dev` (frontend 폴더 내) 비동기 실행
- **검증**: `view_browser` 또는 브라우저 실행을 통해, 흰 공간(바닥) 위에 핑크색/파란색 네모난 조형물들이 겹치지 채 떨어져있고, 그 사이를 지나는 동선 선분이 잘 나타나는지 화면 캡처(렌더 확인)를 통해 점검합니다.
