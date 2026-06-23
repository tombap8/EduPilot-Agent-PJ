# EduPilot Agent Specification (spec.md)

AI 기반 교육 운영 보조 멀티 에이전트 시스템 (Multi-Agent System) **EduPilot Agent**의 기능적/비기능적 요구사항 명세서입니다.

---

## 1. 목적 및 목표 (Objective & Goals)

### 1.1 목적
강사의 행정 및 교수 업무를 혁신적으로 보조하기 위해 강의 자료 검색(RAG), 학생 관리(SQL), 학사 일정 연동(SQL), 코드 리뷰, 공지사항 자동 생성을 통합한 멀티 에이전트 기반의 교육 운영 비서 플랫폼을 구축합니다.

### 1.2 핵심 목표
* **업무 효율화**: 반복적인 학생 상담 요약, 공지 작성, 일정 조회의 자동화.
* **지능형 강의자료 검색 (RAG)**: 업로드된 교재 PDF 파일들에서 신속하고 정확한 정보 출처 제시 및 답변 제공.
* **복합 태스크 처리**: 사용자의 다중 요청(예: "상담 내용 조회 후 공지 작성")을 분석하여 하위 작업으로 쪼개고 병렬 처리하여 최적의 응답 생성.
* **직관적인 모니터링**: 3단 레이아웃 대시보드(Streamlit)를 통해 실시간 관리 기능 제공.

---

## 2. 요구사항 및 기능 범위 (Functional Requirements)

### 2.1 에이전트별 요구사항

#### A. Supervisor Agent (중앙 조정자)
* **역할**: 사용자의 자연어 입력을 분석하고 의도(Intent)를 분류하여 적절한 서브 에이전트(Worker)에게 분배.
* **복합 의도 처리 (Task Decomposition)**: 하나의 질의에 여러 의도가 포함된 경우(예: "김민수 출결 조회하고 다음 주 과제 일정 포함해서 공지 써줘"), 하위 태스크로 나누어 `Student Agent`, `Schedule Agent`, `Notice Agent`를 순차적 혹은 병렬 호출.
* **비동기 처리**: `asyncio.gather`를 활용해 다중 에이전트 호출 성능 최적화.

#### B. Lecture Agent (RAG 강의자료 검색)
* **역할**: 기술 서적 및 평가기준 문서(PDF)를 기반으로 사용자 질문에 답하고, 정확한 출처(파일명 및 페이지)를 명시.
* **대상 자료**: 
  * Tech_books: `React.pdf`, `JS.pdf`, `Python.pdf`
  * NCS_critaria: `NCS_평가기준.pdf`
  * NCS_books 하위 PDF 문서들
* **기술 스펙**: LangChain RecursiveCharacterTextSplitter, Chroma VectorDB, OpenAI Embeddings (`text-embedding-3-small` 또는 유사 모델).

#### C. Student Agent (자연어-to-SQL 학생 관리)
* **역할**: 자연어로 들어오는 학생 정보 및 출결 질의를 SQL로 변환하여 SQLite DB를 조회.
* **조회 시나리오**:
  * 특정 학생의 출결 상태 및 과제 점수 조회
  * 취업 목적을 가진 학생 목록 조회
  * 최근 상담 일자 및 상담 내용 조회

#### D. Assignment Review Agent (코드 리뷰)
* **역할**: 학생이 제출한 소스코드(텍스트)를 분석하여 리뷰 피드백 제공.
* **분석 범위**: 코드 목적 설명, 구문 오류 및 안티패턴 탐지, 성능 개선 및 리팩토링 방안, 구현 난이도 평가.

#### E. Schedule Agent (학사일정 관리)
* **역할**: 학사일정 데이터베이스(Schedules)에서 주차별 강의 주제, 과제 마감일, 시험 일정 등을 전담 조회.

#### F. Notice Agent (공지사항 자동 생성)
* **역할**: 일정, 과제, 평가 등의 컨텍스트를 활용하여 완성도 높은 공지문 템플릿 작성.
* **출력 포맷**: 메신저(카카오톡 알림톡)나 LMS(교육관리시스템)에 바로 복사하여 사용할 수 있는 서식 제공.

---

## 3. 비기능적 요구사항 (Non-Functional Requirements)

* **성능 및 지연 시간 (Latency)**: 복합 태스크 조회 시 비동기 병렬 처리를 수행하여 LLM 응답 대기시간을 최소화.
* **안정성 및 보안**: API Key 및 중요 환경변수는 `.env` 파일을 통해 로드하며 하드코딩하지 않음.
* **경량 데이터베이스**: 데이터 관리는 이식성이 좋고 가벼운 SQLite3 파일 DB를 활용.
* **확장성**: 추후 새로운 Worker Agent가 손쉽게 추가될 수 있도록 Hub-and-Spoke 구조의 라우팅 모듈 설계.

---

## 4. 사용자 인터페이스 (UI/UX) 명세

Streamlit 기반의 단일 페이지 대시보드를 구축하며, 화면을 **3단 레이아웃**으로 분할합니다.

1. **좌측 사이드바 (Admin & Ingestion)**
   * **데이터베이스 관리**: SQLite DB 기초 데이터 초기화 (Reset & Seed DB 버튼).
   * **자료 업로드**: 새로운 PDF 문서를 업로드하고 실시간으로 VectorDB(Chroma)에 임베딩 처리하는 제어판.
2. **중앙 영역 (Core Chat Interface)**
   * ChatGPT 스타일의 챗봇 대화방. 강사가 자연어로 Supervisor Agent와 상호작용.
3. **우측 대시보드 (Real-time Status Monitor)**
   * **최근 공지사항 피드**: `Notice Agent`가 생성하여 DB에 등록된 최근 공지사항 이력 카드 뷰.
   * **상담 이력 타임라인**: 최근 수행된 학생 상담 요약 내역을 타임라인 카드로 표시.

---

## 5. 제외 범위 (Out of Scope)
* 실제 카카오톡 알림톡 API 연동 발송 기능 (본 프로젝트에서는 템플릿 생성 및 화면 복사 기능까지만 구현).
* 실시간 GitHub Webhook 연동 (코드 분석 에이전트는 사용자가 텍스트 영역에 소스코드를 직접 입력하거나 파일을 올리는 방식으로 제한).
