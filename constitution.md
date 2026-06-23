# EduPilot Agent Constitution (constitution.md)

EduPilot Agent 프로젝트 개발 및 AI 에이전트 동작 시 준수해야 하는 핵심 지침서(DNA)입니다.

---

## 1. 개발 및 코딩 지침 (Coding Standards)

* **에러 헨들링**: 모든 DB 조회, PDF 파싱, LLM API 호출에는 반드시 예외 처리(`try-except`) 블록을 구성하고 사용자 친화적인 메시지를 출력하도록 합니다.
* **비동기 프로그래밍**: Supervisor 에이전트와 서브 에이전트 모듈은 `async/await` 패턴을 일관되게 활용하여 오케스트레이션합니다.
* **보안 및 환경 설정**: API Key 및 로컬 저장 경로는 소스 코드에 하드코딩하지 않으며, 반드시 `dotenv`를 통해 `.env` 파일로부터 안전하게 로드합니다.
* **코드 가독성**: PEP 8 표준을 준수하고, 함수와 클래스에는 간결한 docstring을 기입합니다.

---

## 2. LLM 및 프롬프트 가이드라인 (Prompting Guidelines)

* **역할 규정**: 각 서브 에이전트는 독립된 개성을 지녀야 합니다.
  * **Lecture Agent**: 학술적이고 정확하며 출처를 엄격히 표시합니다.
  * **Student Agent**: DB 정보를 기반으로만 팩트 기반으로 답변하며, 임의로 추측하지 않습니다.
  * **Assignment Agent**: 멘토링 스타일로 따뜻하고 건설적인 피드백을 제공하되 코드 개선 핵심은 명확히 지적합니다.
  * **Notice Agent**: 강사가 수정 없이 복사해서 사용할 수 있도록 정중하고 세련된 존댓말과 정돈된 마크다운을 사용합니다.
* **출처 제시**: PDF RAG 및 SQL 조회 시 가상의 정보를 절대 추가하지 않고(No Hallucination), 근거 데이터를 활용하여 답변 하단에 `[출처: 파일명.pdf / DB]` 형식으로 반드시 명시합니다.

---

## 3. UI/UX 구현 원칙 (UI Principles)

* **3단 레이아웃 일관성**: Streamlit의 `sidebar`와 `columns`를 조화롭게 구성하여 모니터링 대시보드와 대화형 챗봇의 상호작용이 한눈에 들어오도록 설계합니다.
* **시각적 우수성**: Custom CSS를 주입하여 기본 Streamlit 위젯보다 세련된 느낌을 제공하고, 로딩 바(`st.spinner`) 및 상태 피드백을 적절히 제공합니다.
* **세션 관리**: 사용자가 질문을 입력하거나 페이지를 새로고침하더라도 이전 대화 내용 및 공지사항 이력이 유지되도록 `st.session_state`를 체계적으로 관리합니다.
