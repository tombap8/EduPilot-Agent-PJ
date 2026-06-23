# EduPilot Agent Implementation Tasks (tasks.md)

EduPilot Agent 구현을 위한 작업 항목 리스트입니다. 완료된 항목은 `[x]`로 표시합니다.

---

## [ ] Phase 1: AI Spec 설계 문서 작성
- [x] `spec.md` 작성 및 요구사항 정의
- [x] `plan.md` 작성 및 아키텍처 설계
- [x] `constitution.md` 작성 및 개발 표준 수립
- [x] `tasks.md` 작성 및 태스크 정의

## [ ] Phase 2: 인프라 및 환경 구성
- [ ] `.env` 파일 설정 검토 및 로드 검증
- [ ] `requirements.txt` 정의 및 패키지 설치
- [ ] SQLite3 데이터베이스 모듈(`database.py`) 구현
  - [ ] 테이블 생성 스키마 구성 (`students`, `schedules`, `announcements`)
  - [ ] 데모용 초기 Dummy 데이터 적재 스크립트 작성 및 테스트
- [ ] Chroma DB 연동 및 PDF 파싱 파이프라인 구현 (`docs` 디렉토리 자동 스캔)

## [ ] Phase 3: Worker Agent 구현
- [ ] `lecture_agent.py` (Chroma RAG 기반 PDF 검색 및 생성)
- [ ] `student_agent.py` (자연어 -> SQL 질의 변환 및 결과 포맷팅)
- [ ] `assignment_agent.py` (제출된 코드 구문 분석 및 리뷰 피드백)
- [ ] `schedule_agent.py` (학사 일정 DB 조회 및 일정 요약)
- [ ] `notice_agent.py` (컨텍스트 기반 공지사항 자동 템플릿 완성 및 DB 이력 저장)

## [ ] Phase 4: 오케스트레이션 및 Supervisor 연동
- [ ] `supervisor.py` (자연어 의도 분석 및 라우터)
- [ ] `asyncio.gather`를 통한 비동기 병렬 태스크 실행 및 답변 취합 구현

## [ ] Phase 5: Streamlit 웹 애플리케이션 및 모니터링 UI 구축
- [ ] `app.py` 기본 레이아웃 구성 (Sidebar / Chat / Dashboard)
- [ ] 사이드바: DB 리셋 버튼, 신규 PDF 파일 업로드 및 실시간 RAG 임베딩 트리거
- [ ] 중앙: ChatGPT 스타일 챗봇 세션 상태 기반 렌더링 및 입력 필드 연동
- [ ] 우측: 공지사항 피드 리스트 및 최근 상담 이력 요약 타임라인
- [ ] 최종 5단계 데모 시나리오 검증 및 QA 진행
