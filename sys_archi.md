# EduPilot Agent 시스템 아키텍처 구성도 (sys_archi.md)

EduPilot Agent는 교육 기관의 강사 및 운영진을 위한 **AI 기반 멀티 에이전트 시스템 포털**입니다. 본 문서는 시스템의 주요 레이어, 구성 요소 간의 관계, 데이터 흐름 및 핵심 설계 패턴을 설명합니다.

---

## 1. 시스템 아키텍처 다이어그램 (Mermaid)

EduPilot Agent는 중앙의 **Supervisor Agent**가 사용자의 복합 질의를 분석 및 분해하여, 다수의 전문 **Worker Agent**에게 작업을 배분하고 결과를 비동기적으로 취합하는 **Hub-and-Spoke 멀티 에이전트 아키텍처**를 따릅니다.

```mermaid
graph TD
    %% Presentation Layer
    subgraph UI ["Presentation Layer (Streamlit UI)"]
        Streamlit["app.py (Streamlit Web App)"]
        Sidebar["Left Sidebar: Admin & Ingestion (PDF Ingestion, DB Seed)"]
        ChatArea["Center Area: Conversational Chat Interface"]
        Dashboard["Right Sidebar: Status Dashboard (Announcements, Consultations)"]
    end

    %% Orchestration Layer
    subgraph Orchestrator ["Orchestration Layer (Supervisor)"]
        Supervisor["agents/supervisor.py<br/>(Supervisor Agent)"]
    end

    %% Worker Agents Layer
    subgraph Workers ["Worker Agents Layer (Specialized Agents)"]
        LectureAgent["agents/lecture_agent.py<br/>(Lecture Agent - RAG)"]
        StudentAgent["agents/student_agent.py<br/>(Student Agent - SQL)"]
        ScheduleAgent["agents/schedule_agent.py<br/>(Schedule Agent - SQL)"]
        CourseAgent["agents/course_agent.py<br/>(Course Agent - Designer)"]
        GradingAgent["agents/grading_agent.py<br/>(Grading Agent - Evaluator)"]
        AssignmentAgent["agents/assignment_agent.py<br/>(Assignment Agent - Code Review)"]
        NoticeAgent["agents/notice_agent.py<br/>(Notice Agent - Messenger)"]
    end

    %% Storage & Database Layer
    subgraph Data ["Database & Storage Layer"]
        SQLiteDB[("SQLite Database<br/>(edupilot.db)")]
        ChromaDB[("Chroma Vector DB<br/>(chroma_db)")]
        PDFDocs[("Local PDF Documents<br/>(docs/)")]
    end

    %% Relationships
    Streamlit -->|1. User Prompt / Actions| Supervisor
    Streamlit -->|DB Reset / Upload PDF| SQLiteDB
    Streamlit -->|Upload PDF| PDFDocs

    Supervisor -->|2. Task Analysis & Planning (JSON)| Supervisor
    Supervisor -->|3a. Query (RAG)| LectureAgent
    Supervisor -->|3b. Query (Student Info)| StudentAgent
    Supervisor -->|3c. Query (Schedules)| ScheduleAgent
    Supervisor -->|3d. Request Design| CourseAgent
    Supervisor -->|3e. Request Grading| GradingAgent
    Supervisor -->|3f. Source Code| AssignmentAgent
    Supervisor -->|3g. Formulate Message (with context)| NoticeAgent

    %% Agent Database interactions
    LectureAgent -->|Read Chunks| ChromaDB
    PDFDocs -->|Embedding Ingestion| ChromaDB
    StudentAgent -->|Query / Read| SQLiteDB
    ScheduleAgent -->|Query / Read| SQLiteDB
    CourseAgent -->|Read / Write Course & Exam| SQLiteDB
    GradingAgent -->|Read / Write Submissions| SQLiteDB
    NoticeAgent -->|Write Announcements| SQLiteDB

    %% Responses returning back
    LectureAgent -->|Response| Supervisor
    StudentAgent -->|Response| Supervisor
    ScheduleAgent -->|Response| Supervisor
    CourseAgent -->|Response| Supervisor
    GradingAgent -->|Response| Supervisor
    AssignmentAgent -->|Response| Supervisor
    NoticeAgent -->|Response| Supervisor

    Supervisor -->|4. Synthesized MD Report| Streamlit
    SQLiteDB -.->|Dynamic Read / Refresh| Dashboard
```

---

## 2. 레이어별 구성 요소 (Layered Architecture Components)

### 2.1 Presentation Layer (사용자 인터페이스)
*   **[app.py](file:///c:/Users/tomba/OneDrive/문서/GitHub/EduPilot-Agent-PJ/app.py)**: Streamlit 프레임워크를 기반으로 구축된 웹 포털 페이지입니다.
    *   **3단 반응형 레이아웃**:
        1.  **좌측 사이드바**: 데이터베이스 강제 리셋, 샘플 데이터 적재(Seed DB), 신규 PDF 교재 업로드 및 임베딩 처리 제어.
        2.  **중앙 영역**: 챗봇 인터페이스로, 강사가 자연어로 질문하거나 코드를 제출하여 피드백을 수신.
        3.  **우측 대시보드**: DB의 `announcements` 및 `students` 상담 테이블과 연동되어 생성된 공지사항 및 상담 이력을 타임라인 카드 뷰로 시각화.
    *   **Tailwind CSS v3**: CDN을 활용하여 Streamlit 내부 HTML에 스타일을 강제 주입하여 미려한 고정형 내비게이션 바, 카드 뷰, 타임라인 및 마이크로 애니메이션을 제공합니다.

### 2.2 Orchestration Layer (중앙 조정 및 흐름 제어)
*   **[supervisor.py](file:///c:/Users/tomba/OneDrive/문서/GitHub/EduPilot-Agent-PJ/agents/supervisor.py)**: 시스템의 허브 역할을 하며, 강사로부터 전달받은 복합 질문을 분석하고 하위 작업들을 수립합니다.
    *   **작업 분해 (Task Decomposition)**: LLM(GPT-4o-mini)을 사용하여 자연어 요구사항을 에이전트 매핑, 질의 내용, 실행 의존성(`depends_on_steps`)을 정의한 JSON 계획서로 변환합니다.
    *   **비동기 태스크 병렬 처리**: `asyncio.create_task`와 `asyncio.gather`를 활용해, 의존성이 없는 에이전트 호출(예: 학생 정보 조회와 학사 일정 조회)을 병렬로 동시 수행하여 API 대기 시간(Latency)을 최소화합니다.
    *   **컨텍스트 전파**: 선행 태스크의 결과값(예: 학생 출결 데이터)을 후행 태스크(예: 공지사항 작성)의 추가 컨텍스트로 결합하여 에이전트 간 협업을 실현합니다.

### 2.3 Worker Agent Layer (개별 영역 전문 에이전트)
각 에이전트는 독립된 스크립트로 동작하며, Supervisor의 요청에 따라 동작합니다.

1.  **Lecture Agent ([lecture_agent.py](file:///c:/Users/tomba/OneDrive/문서/GitHub/EduPilot-Agent-PJ/agents/lecture_agent.py))**
    *   **기술/역할**: 정밀 RAG(Retrieval-Augmented Generation) 시스템.
    *   **동작**: `docs/` 디렉토리 내의 PDF 교재(`JS.pdf`, `Python.pdf`, `React.pdf`, `NCS_평가기준.pdf` 등)를 로드하여 텍스트 청킹 후, `Chroma DB` 벡터스토어에서 코사인 유사도 검색을 수행합니다. 답변 생성 시 정확한 출처 정보(파일명 및 페이지)를 반드시 하단에 출력해 환각 현상을 억제합니다.
2.  **Student Agent ([student_agent.py](file:///c:/Users/tomba/OneDrive/문서/GitHub/EduPilot-Agent-PJ/agents/student_agent.py))**
    *   **기술/역할**: Text-to-SQL 변환 조회 시스템.
    *   **동작**: 사용자의 학생 조회 자연어를 안전한 SQLite SELECT 쿼리로 변환하고, 데이터베이스에서 조회한 딕셔너리 데이터를 바탕으로 한국어 존댓말 보고 답변을 최종 생성합니다.
3.  **Schedule Agent ([schedule_agent.py](file:///c:/Users/tomba/OneDrive/문서/GitHub/EduPilot-Agent-PJ/agents/schedule_agent.py))**
    *   **기술/역할**: 학사 일정 조회 및 공휴일 동기화 시스템.
    *   **동작**: 데이터베이스 내 `schedules` 테이블을 쿼리하여 주차별 강의 주제나 마감일 정보를 가져옵니다. 2026~2030년 대한민국 법정 공휴일 목록을 내장하여 실제 교육과정 운영 시작일로부터 완료일까지의 날짜를 계산하는 로직을 보조합니다.
4.  **Course Agent ([course_agent.py](file:///c:/Users/tomba/OneDrive/문서/GitHub/EduPilot-Agent-PJ/agents/course_agent.py))**
    *   **기술/역할**: 교육과정(Curriculum) 설계 및 평가(Exam) 문제 출제 빌더.
    *   **동작**: 주차별 핵심 커리큘럼 생성, 상세 강의계획안(마크다운), 5문항의 평가 시험(객관식 3문항, 서술형 1문항, 코딩 1문항) 등을 자동 저작하여 SQLite DB에 저장합니다.
5.  **Grading Agent ([grading_agent.py](file:///c:/Users/tomba/OneDrive/문서/GitHub/EduPilot-Agent-PJ/agents/grading_agent.py))**
    *   **기술/역할**: AI 자동 시험 채점 및 피드백 리포트 생성기.
    *   **동작**: 학생이 제출한 주관식 및 코딩 답안의 핵심 키워드를 비교 분석하고, 부분 점수를 부여하여 상세 피드백 리포트를 XML/JSON 파싱 구조로 구성합니다.
6.  **Assignment Review Agent ([assignment_agent.py](file:///c:/Users/tomba/OneDrive/문서/GitHub/EduPilot-Agent-PJ/agents/assignment_agent.py))**
    *   **기술/역할**: 코드 가독성/구문 에러/안티패턴 정적 리뷰어.
    *   **동작**: 강사 또는 학생이 제출한 완성 코드를 분석하여 성능 최적화, 보안 위협, 변수 명명법 가이드를 작성합니다.
7.  **Notice Agent ([notice_agent.py](file:///c:/Users/tomba/OneDrive/문서/GitHub/EduPilot-Agent-PJ/agents/notice_agent.py))**
    *   **기술/역할**: 알림톡 / LMS 공지 템플릿 생성기.
    *   **동작**: Supervisor가 전달한 타 에이전트의 수행 결과(출결 저조자 명단, 다음 주 평가 일정 등)를 활용하여 정형화된 공지 서식 템플릿을 자동으로 작성하고 이를 데이터베이스에 등록합니다.

### 2.4 Database & Storage Layer (데이터 관리)
시스템 상태 및 벡터 정보를 관리하기 위해 두 종류의 데이터베이스가 로컬 환경에 상주합니다.

*   **SQLite RDBMS ([database.py](file:///c:/Users/tomba/OneDrive/문서/GitHub/EduPilot-Agent-PJ/database.py))**
    *   **edupilot.db**: 이식성이 뛰어난 로컬 단일 파일 관계형 데이터베이스입니다.
    *   **스키마 구성**:
        *   `students`: ID, 학생명, 출결횟수, 과제점수, 상담일지, 취업진로, 최종상담일.
        *   `schedules`: ID, 주차, 대주제, 과제마감일, 시험일정.
        *   `announcements`: ID, 공지 제목, 공지 내용, 작성 시각.
        *   `courses`: ID, 과정명, 과정설명, 총 시수, 개강일, 수료일, 일일 수업시간, 수강 시 제외할 공휴일 목록.
        *   `curriculums`: ID, 과정 ID, 주차, 대주제, 상세 키워드.
        *   `lecture_plans`: ID, 과정 ID, 과목명, 강의안 상세 내용 (Markdown).
        *   `exams`: ID, 과정 ID, 과목명, 문제 은행 (JSON array), 활성화 상태 (`ready`/`active`/`closed`).
        *   `exam_submissions`: ID, 시험 ID, 학생명, 제출한 답안 (JSON), 획득 점수, AI 채점 피드백 리포트, 제출 시각.
*   **Chroma Vector DB**
    *   **chroma_db**: `docs/` 내의 강의 도서 자료들이 OpenAI Embeddings (`text-embedding-3-small`)를 통해 벡터화되어 로컬 디렉토리에 영구 저장(Persist)된 로컬 벡터 데이터베이스입니다.

---

## 3. 대표 데이터 흐름 (Data Flow Scenario)

### 3.1 복합 요청 처리 프로세스
*강사의 입력: "박철수의 최근 성적을 확인하고 다음 주 일요일 과제 일정을 합쳐서 학부모 전송용 공지를 만들어줘."*

```
[강사] -> (자연어 질의 입력) -> [Streamlit Web UI (app.py)]
                                        |
                               (비동기 워크플로우 호출)
                                        v
                            [Supervisor (supervisor.py)]
                                        |
                 1. 실행 계획 생성 (GPT-4o-mini를 통한 작업 분해 JSON)
                 {
                    "steps": [
                       {"step_id": 1, "agent": "student_agent", "query": "박철수 성적 조회", "depends_on_steps": []},
                       {"step_id": 2, "agent": "schedule_agent", "query": "다음 주 과제 마감 일정", "depends_on_steps": []},
                       {"step_id": 3, "agent": "notice_agent", "query": "학부모 전송용 공지 작성", "depends_on_steps": [1, 2]}
                    ]
                 }
                                        |
                      2. 비동기 병렬 실행 (asyncio.gather)
                        +-------------------------------+
                        | (병렬)                         | (병렬)
                        v                               v
            [Student Agent]                  [Schedule Agent]
              (Text-to-SQL)                    (SQLite SQL)
                        |                               |
              SELECT assignment_score          SELECT assignment_due 
              FROM students ...                FROM schedules ...
                        |                               |
                        +---------------+---------------+
                                        | (각각의 응답 회수 및 병합)
                                        v
                         3. 후행 의존 태스크 비동기 예약 실행
                                        | (Step 1, 2 결과를 context_str로 전달)
                                        v
                                 [Notice Agent]
                                        |
                       4. 공지 템플릿 생성 및 SQLite 저장
                                        |
                            (최종 결과 종합 보고서 작성)
                                        v
[강사] <--- (마크다운 종합 결과 화면 출력) <--- [Streamlit UI]
```

---

## 4. 시스템 설계의 강점 (Key Architectural Strengths)

1.  **비동기 병렬 처리 최적화**: Python의 `asyncio` 라이브러리를 통해 독립적인 서브 에이전트 간의 I/O 바운드 작업(예: LLM API 호출, 로컬 DB 쿼리)을 병렬 처리함으로써 성능 저하 요인을 구조적으로 극복했습니다.
2.  **보안이 보장된 Text-to-SQL**: `Student Agent` 및 `Schedule Agent`는 생성된 SQL이 `SELECT` 문으로 시작하는지 정적 필터링을 거치게 설계되어 데이터 변조 및 위협을 방지합니다.
3.  **정밀도 높은 RAG & 역추적**: PDF 청크 수집 시 파일명과 실제 물리 페이지 번호를 메타데이터로 추적하여, 답변 출력 시 사용자가 출처를 한눈에 확인할 수 있게 구현하여 시스템의 정합성을 높였습니다.
4.  **유연한 확장성**: 새로운 Worker Agent가 필요할 때 `supervisor.py` 프롬프트에 이름과 역할을 추가하고, `execute_step` 함수에 라우팅 처리만 더해주면 기존 프론트엔드나 DB 스키마 수정 없이 간편하게 확장할 수 있습니다.
