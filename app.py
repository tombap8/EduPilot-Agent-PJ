import os
import streamlit as st
import asyncio
import pandas as pd
from dotenv import load_dotenv

# 데이터베이스 조작용 API 임포트
from database import (
    init_db, get_all_students, get_all_announcements,
    get_all_courses, get_course_curriculum, get_course_lecture_plans,
    get_all_exams_with_course, get_exam_submissions, get_all_submissions,
    insert_course, insert_curriculum, insert_lecture_plan, insert_exam, insert_submission,
    get_exam_by_id, update_exam_status, get_active_exams, has_student_submitted, get_student_info
)
# 에이전트 API 임포트
from agents.supervisor import run_supervisor_workflow
from agents.course_agent import generate_curriculum_async, generate_lecture_plan_async, generate_exam_async, generate_single_question_async
from agents.grading_agent import grade_exam_submission_async

load_dotenv()

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# Streamlit 페이지 기본 설정
st.set_page_config(
    page_title="EduPilot Agent - 강사의 두 번째 뇌",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 세션 상태 초기화 (로그인 상태)
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.role = None      # 'teacher' or 'student'
    st.session_state.username = None  # '교사' 또는 학생 이름

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "안녕하세요! 교육 운영 보조 멀티 에이전트 **EduPilot Agent**입니다. 무엇을 도와드릴까요?"}
    ]

if "pending_questions" not in st.session_state:
    st.session_state.pending_questions = None

if "pending_exam_metadata" not in st.session_state:
    st.session_state.pending_exam_metadata = None

if "view_submission_detail" not in st.session_state:
    st.session_state.view_submission_detail = None


def render_detailed_scorecard(questions: list, student_answers: list, feedback_raw: str):
    import json
    
    # 1. JSON 파싱 시도
    is_json = False
    fb_data = {}
    try:
        fb_data = json.loads(feedback_raw)
        is_json = True
    except Exception:
        # JSON이 아닌 경우 (기존 마크다운 피드백)
        st.markdown(feedback_raw)
        return
        
    # 2. 구조화된 채점 렌더링
    st.markdown("---")
    st.markdown("### 📊 AI 상세 채점 리포트 카드")
    
    q_reports = fb_data.get("q_reports", {})
    calc_score = sum(int(q_reports.get(num, {}).get("score", 0)) for num in q_reports)
    
    sc1, sc2 = st.columns([1, 4])
    with sc1:
        st.metric(label="최종 획득 점수", value=f"{calc_score}점")
    with sc2:
        st.info(f"**💡 AI 총평**\n\n{fb_data.get('overall_comment', '평가 요약이 없습니다.')}")
        
    st.markdown("#### 🔍 문항별 세부 결과")
    
    for q in questions:
        q_num = str(q["number"])
        q_report = q_reports.get(q_num, {})
        student_ans_val = next((a["answer"] for a in student_answers if a["number"] == q["number"]), "제출 답안 없음")
        score_val = q_report.get("score", 0)
        
        # 문항 컨테이너
        with st.container(border=True):
            if q["type"] == "choice":
                is_correct = (str(student_ans_val) == str(q["answer"]))
                icon = "✅ 정답" if is_correct else "❌ 오답"
                color = "green" if is_correct else "red"
                
                st.markdown(f"##### **문항 {q['number']}. {q['question']}** (객관식)")
                
                # 보기 표시
                for opt in q.get("options", []):
                    # 학생 답안 강조 표시
                    if opt.startswith(str(student_ans_val)):
                        st.markdown(f"- **{opt} (수강생 선택)**")
                    else:
                        st.markdown(f"- {opt}")
                
                col_ans, col_exp = st.columns([1, 2])
                with col_ans:
                    st.markdown(f"🎯 **모범 정답**: `{q['answer']}`번")
                    st.markdown(f"📊 **채점**: :{color}[**{icon} (+{score_val}점)**]")
                with col_exp:
                    st.markdown(f"💡 **상세 해설**:")
                    st.caption(q.get("explanation", "등록된 상세 해설이 없습니다."))
            else:
                # 서술형 및 코딩형
                q_type_ko = "주관식 서술형" if q["type"] == "descriptive" else "코딩실습형"
                st.markdown(f"##### **문항 {q['number']}. {q['question']}** ({q_type_ko})")
                
                st.markdown(f"✍️ **수강생 제출 답안**:")
                st.code(student_ans_val, language="python" if q["type"] == "coding" else "")
                
                col_info, col_exp = st.columns(2)
                with col_info:
                    st.markdown(f"🔑 **🔑 채점 기준 키워드**: `{', '.join(q.get('keywords', []))}`")
                    st.markdown(f"📖 **📖 모범 답안 가이드**:")
                    st.success(q.get("answer_guide", ""))
                with col_exp:
                    st.markdown(f"💡 **상세 해설**:")
                    st.caption(q.get("explanation", "등록된 상세 해설이 없습니다."))
                
                # 점수 및 피드백 요약
                st.markdown(f"📊 **채점**: :orange[**배점 {score_val}점** / 20점]")
                if q_report.get("feedback"):
                    st.markdown(f"🤖 **AI 개별 피드백**: {q_report['feedback']}")


# ---------------------------------------------

# 0. 로그인 게이트웨이 화면 (Landing Login Screen)
# ---------------------------------------------
if not st.session_state.logged_in:
    st.markdown("<br><br>", unsafe_allow_html=True)
    l_col1, l_col2, l_col3 = st.columns([1, 1.5, 1])
    
    with l_col2:
        with st.container(border=True):
            logo_path = os.path.join(PROJECT_ROOT, "edupilot_logo.png")
            if os.path.exists(logo_path):
                st.image(logo_path, width=90)
            else:
                st.markdown("## 🎓")
            st.title("🤖 EduPilot Agent")
            st.subheader("지능형 교육 정보 플랫폼 로그인")
            st.markdown("강사 및 학생 인증 후 서비스를 이용하실 수 있습니다.")
            st.markdown("---")
            
            login_id = st.text_input("아이디 (강사는 '교사', 학생은 본인 이름 입력)", placeholder="이름을 입력해 주세요.")
            login_pw = st.text_input("비밀번호 (전체 기본값: 1111)", type="password", placeholder="비밀번호를 입력해 주세요.")
            submit_login = st.button("🚪 로그인 실행", use_container_width=True)
            
            if submit_login:
                if login_pw != "1111":
                    st.error("❌ 비밀번호가 올바르지 않습니다.")
                elif login_id == "교사":
                    st.session_state.logged_in = True
                    st.session_state.role = "teacher"
                    st.session_state.username = "교사"
                    st.success("✔️ 교사(강사) 계정으로 인증되었습니다. 포털로 진입합니다.")
                    st.rerun()
                else:
                    # 학생 정보 DB 조회 검증
                    student_db_info = get_student_info(login_id)
                    if student_db_info:
                        st.session_state.logged_in = True
                        st.session_state.role = "student"
                        st.session_state.username = login_id
                        st.success(f"✔️ {login_id} 학생으로 인증되었습니다. 시험 포털로 진입합니다.")
                        st.rerun()
                    else:
                        st.error("❌ 등록되지 않은 학생 이름입니다. 강사 대시보드에 학생 정보가 등록되어 있는지 확인해 주세요.")
    st.stop() # 로그인이 완료될 때까지 아래 본문 렌더링 중지

# ---------------------------------------------
# 1. 사이드바 구성 (환영 표시 및 로그아웃 + 권한 격리)
# ---------------------------------------------
with st.sidebar:
    logo_path = os.path.join(PROJECT_ROOT, "edupilot_logo.png")
    if os.path.exists(logo_path):
        st.image(logo_path, width=60)
    else:
        st.markdown("## 🎓")
    st.title("EduPilot Platform")
    
    # 로그인 정보 & 로그아웃 버튼
    role_ko = "교사/강사" if st.session_state.role == "teacher" else "수강생"
    st.markdown(f"👤 **{st.session_state.username}** 님 환영합니다!")
    st.caption(f"접속 권한: {role_ko}")
    
    if st.button("🚪 로그아웃", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.role = None
        st.session_state.username = None
        st.session_state.messages = [
            {"role": "assistant", "content": "안녕하세요! 교육 운영 보조 멀티 에이전트 **EduPilot Agent**입니다. 무엇을 도와드릴까요?"}
        ]
        st.rerun()
        
    st.markdown("---")

    # 강사용 권한에만 관리 툴 오픈
    if st.session_state.role == "teacher":
        st.subheader("🗄️ 데이터베이스 관리")
        if st.button("🔄 DB 초기화 및 더미 데이터 적재", use_container_width=True):
            with st.spinner("DB 초기화 중..."):
                init_db(force_reset=True)
            st.success("DB가 완벽히 초기화되었습니다!")
            st.rerun()

        st.markdown("---")
        st.subheader("📚 강의 자료 PDF 업로드")
        uploaded_files = st.file_uploader(
            "추가 교재 문서를 업로드해 주세요.",
            type=["pdf"],
            accept_multiple_files=True
        )
        if uploaded_files:
            save_count = 0
            for f in uploaded_files:
                target_path = os.path.join(PROJECT_ROOT, "docs", "Tech_books", f.name)
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                with open(target_path, "wb") as out_file:
                    out_file.write(f.read())
                save_count += 1
            if save_count > 0:
                from agents.lecture_agent import ingest_documents
                with st.spinner("PDF 문서 파싱 및 임베딩 진행 중..."):
                    chunk_count = ingest_documents()
                st.success(f"{save_count}개 파일 업로드 & {chunk_count}개 반영 완료!")
                st.rerun()

        st.markdown("---")
        st.subheader("📡 강의자료 적재 현황")
        from agents.lecture_agent import find_all_pdfs, DOCS_DIR
        try:
            pdfs = find_all_pdfs(DOCS_DIR)
            display_pdfs = [os.path.basename(p) for p in pdfs if os.path.basename(p) != "edupilot_project_proposal.pdf"]
            st.write(f"현재 로드된 PDF 파일 수: **{len(display_pdfs)}**개")
            for filename in display_pdfs:
                st.caption(f"• {filename}")
        except:
            st.caption("PDF 없음")
    else:
        st.markdown("### 📝 안내 사항")
        st.markdown(
            "학생 포털에 오신 것을 환영합니다.\n\n"
            "강사님이 출제하고 **[시험 시작]**을 선언한 활성 평가 시험지만 화면에 나타납니다.\n"
            "평가를 성실히 수행하시고 답안을 전송하면 중복 제출 방지를 위해 시험지가 자동으로 마감처리됩니다."
        )

# ---------------------------------------------
# 2. 강사 업무 포털 (Teacher Portal)
# ---------------------------------------------
if st.session_state.role == "teacher":
    col_chat, col_status = st.columns([2, 1], gap="medium")

    with col_chat:
        st.title("👩‍🏫 EduPilot 강사용 업무 포털")
        st.markdown("교육과정 개설, 상세 강의계획안 도출, 시험 시작/종료 관리 및 학생 성적 조회를 관제합니다.")
        st.markdown("---")

        tab_chat, tab_course, tab_exam = st.tabs([
            "🤖 에이전트 챗봇", 
            "🆕 교육과정 개설 & 강의 설계", 
            "📊 시험 출제 및 평가 관리"
        ])

        # --- 탭 1: 에이전트 챗봇 ---
        with tab_chat:
            with st.container(border=True):
                st.markdown("### 👋 지능형 교육 조력자 EduPilot Agent")
                st.markdown("자연어로 질문하면 하단 6가지 전문 에이전트가 협업해 최적의 교안과 리포트를 설계합니다.")
                
                f_col1, f_col2, f_col3 = st.columns(3)
                with f_col1:
                    st.markdown("📚 **Lecture RAG**: 교재 PDF 정밀 출처 검색")
                    st.markdown("🗄️ **Student SQL**: 학생 출결/상담 DB 조회")
                with f_col2:
                    st.markdown("💻 **Assignment**: 소스코드 결함/리팩토링 분석")
                    st.markdown("📅 **Schedule**: 과제 마감 및 학사일정 조회")
                with f_col3:
                    st.markdown("📢 **Notice**: 수집 정보 통합 공지문 완성")
                    st.markdown("🏫 **Course**: 커리큘럼/강의안/시험 자동 저작")

            st.markdown("---")
            for msg in st.session_state.messages:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])

            if prompt := st.chat_input("김민수 출결 확인해보고 학부모 공지문 써줘..."):
                st.chat_message("user").markdown(prompt)
                st.session_state.messages.append({"role": "user", "content": prompt})
                with st.chat_message("assistant"):
                    with st.spinner("Supervisor가 에이전트 조율을 계획 중입니다..."):
                        try:
                            response = asyncio.run(run_supervisor_workflow(prompt))
                            st.markdown(response)
                        except Exception as e:
                            response = f"에이전트 실행 중 오류가 발생했습니다: {e}"
                            st.error(response)
                    st.session_state.messages.append({"role": "assistant", "content": response})
                    st.rerun()

        # --- 탭 2: 교육과정 개설 및 강의 설계 ---
        with tab_course:
            st.subheader("🏫 1. 신규 교육과정 개설 & 커리큘럼 설계")
            with st.form("new_course_form"):
                new_course_name = st.text_input("과정 이름 입력", placeholder="예: FastAPI 파이썬 웹 백엔드 실무 과정")
                new_course_desc = st.text_area("과정 개요 및 설명", placeholder="예: 파이썬을 기반으로 FastAPI와 SQLite DB를 활용한 백엔드 구축 교육")
                submit_course = st.form_submit_button("🆕 과정 등록 및 AI 커리큘럼 생성")
                
            if submit_course and new_course_name:
                with st.spinner("Course 에이전트가 8주 커리큘럼을 생성하고 있습니다..."):
                    curr_list = asyncio.run(generate_curriculum_async(new_course_name, new_course_desc))
                    c_id = insert_course(new_course_name, new_course_desc)
                    for item in curr_list:
                        insert_curriculum(c_id, item["week"], item["topic"], item["details"])
                st.success(f"교육과정 '{new_course_name}'이 등록되고 8주 커리큘럼이 구축되었습니다!")
                st.rerun()

            st.markdown("---")
            st.subheader("📚 2. 개설된 교육과정 조회 및 주차별 강의안 생성")
            courses = get_all_courses()
            if courses:
                for c in courses:
                    with st.expander(f"📖 {c['name']} (과정 ID: {c['id']})"):
                        st.write(f"**과정 개요**: {c['description']}")
                        curr_data = get_course_curriculum(c['id'])
                        
                        st.markdown("**[주차별 커리큘럼 상세]**")
                        for cur in curr_data:
                            st.write(f"- **{cur['week']}주차**: {cur['topic']}")
                            st.caption(f"  * 세부내용: {cur['details']}")
                        
                        st.markdown("**[주간 강의 계획안 조회]**")
                        plans = get_course_lecture_plans(c['id'])
                        if plans:
                            st.info(f"작성 완료된 강의안 수: {len(plans)}개")
                            for p in plans:
                                with st.container(border=True):
                                    st.markdown(f"**과목/주제**: {p['subject_name']}")
                                    st.markdown(p['plan_content'])
                        
                        target_week = st.number_input(f"강의안을 작성할 주차 선택 ({c['name']})", min_value=1, max_value=8, value=1, key=f"week_inp_{c['id']}")
                        target_curr = next((item for item in curr_data if item["week"] == target_week), None)
                        
                        if target_curr:
                            if st.button(f"⚡ {target_week}주차 상세 강의안 AI 자동 생성", key=f"btn_plan_{c['id']}"):
                                with st.spinner(f"{target_week}주차 상세 마크다운 강의안을 생성하는 중..."):
                                    plan_markdown = asyncio.run(generate_lecture_plan_async(
                                        c['name'], target_week, target_curr['topic'], target_curr['details']
                                    ))
                                    insert_lecture_plan(c['id'], f"{target_week}주차 - {target_curr['topic']}", plan_markdown)
                                st.success("강의안이 성공적으로 등록되었습니다!")
                                st.rerun()
            else:
                st.info("개설된 교육과정이 없습니다.")

        # --- 탭 3: 시험 출제 및 평가 관리 ---
        with tab_exam:
            st.subheader("📝 1. 과정별 평가 시험 출제")
            
            if st.session_state.pending_questions is not None:
                st.warning("⚠️ 현재 작성 중인 임시 시험지 미리보기가 하단에 활성화되어 있습니다. 먼저 배포를 완료하거나 출제 취소를 눌러주세요.")
            else:
                courses_list = get_all_courses()
                if courses_list:
                    with st.form("new_exam_form"):
                        selected_c = st.selectbox("대상 교육과정 선택", courses_list, format_func=lambda x: x["name"])
                        exam_subject = st.text_input("시험 과목/평가명 입력", placeholder="예: FastAPI 기초 평가")
                        exam_topics = st.text_input("출제 핵심 키워드 입력", placeholder="예: 라우팅, Path Parameter")
                        submit_exam = st.form_submit_button("⚡ 시험문제 AI 자동 출제")
                        
                    if submit_exam and exam_subject:
                        with st.spinner("Course 에이전트가 시험문제를 자동 출제 중입니다..."):
                            q_list = asyncio.run(generate_exam_async(selected_c["name"], exam_subject, exam_topics))
                            st.session_state.pending_questions = q_list
                            st.session_state.pending_exam_metadata = {
                                "course_id": selected_c["id"],
                                "course_name": selected_c["name"],
                                "subject": exam_subject,
                                "topics": exam_topics
                            }
                        st.success(f"'{exam_subject}' 시험지 가출제가 완료되었습니다. 아래 미리보기 창에서 최종 확인 및 개별 문항 교체가 가능합니다.")
                        st.rerun()
                else:
                    st.info("시험지를 출제할 교육과정이 없습니다.")

            # 미리보기 및 개별 문항 편집기 노출
            if st.session_state.pending_questions is not None:
                st.markdown("---")
                st.subheader("🔍 출제 문제 미리보기 및 편집")
                meta = st.session_state.pending_exam_metadata
                st.info(f"**대상 과정**: {meta['course_name']} | **시험명**: {meta['subject']} | **출제 키워드**: {meta['topics']}")
                
                updated_questions = list(st.session_state.pending_questions)
                for idx, q in enumerate(updated_questions):
                    with st.container(border=True):
                        q_type_ko = "객관식" if q["type"] == "choice" else "주관식 서술형" if q["type"] == "descriptive" else "코딩실습형"
                        st.markdown(f"##### **문항 {q['number']}. {q['question']}** ({q_type_ko})")
                        
                        if q["type"] == "choice":
                            for opt in q.get("options", []):
                                st.write(f"- {opt}")
                            st.markdown(f"🎯 **모범 정답**: `{q['answer']}`번")
                        else:
                            st.markdown(f"🔑 **채점 키워드**: `{', '.join(q.get('keywords', []))}`")
                            st.markdown(f"📖 **모범 답안 가이드**: {q.get('answer_guide', '')}")
                            
                        st.markdown(f"💡 **상세 해설**: {q.get('explanation', '등록된 해설이 없습니다.')}")
                        
                        # 개별 문항 교체 버튼
                        if st.button(f"🔄 {q['number']}번 문항 교체", key=f"btn_replace_q_{idx}"):
                            with st.spinner(f"{q['number']}번 문항을 새로운 문항으로 다시 출제하고 있습니다..."):
                                new_q = asyncio.run(generate_single_question_async(
                                    meta["course_name"], meta["subject"], q["number"], q["type"], meta["topics"]
                                ))
                                updated_questions[idx] = new_q
                                st.session_state.pending_questions = updated_questions
                                st.success(f"{q['number']}번 문항 교체 완료!")
                                st.rerun()
                
                st.markdown("<br>", unsafe_allow_html=True)
                btn_col1, btn_col2 = st.columns(2)
                with btn_col1:
                    if st.button("💾 시험지 최종 배포 및 등록", type="primary", use_container_width=True):
                        # DB에 영구 적재
                        insert_id = insert_exam(meta["course_id"], meta["subject"], st.session_state.pending_questions)
                        st.session_state.pending_questions = None
                        st.session_state.pending_exam_metadata = None
                        st.success(f"시험지가 성공적으로 배포 및 등록되었습니다! (ID: {insert_id})")
                        st.rerun()
                with btn_col2:
                    if st.button("❌ 출제 취소", use_container_width=True):
                        st.session_state.pending_questions = None
                        st.session_state.pending_exam_metadata = None
                        st.warning("시험 출제가 취소되었습니다.")
                        st.rerun()

            st.markdown("---")
            # 🌟 [개선] 시험 시작 및 종료 라이프사이클 제어
            st.subheader("🔄 2. 시험 시작 및 마감 제어판 (Lifecycle Control)")
            exams = get_all_exams_with_course()
            if exams:
                for ex in exams:
                    with st.container(border=True):
                        ec1, ec2, ec3 = st.columns([2, 1, 1.5])
                        with ec1:
                            status_icons = {"ready": "⚪ 대기중", "active": "🟢 시험 시행중", "closed": "🔒 시험 종료됨"}
                            st.markdown(f"**[{ex['course_name']}] {ex['subject_name']}**")
                            st.write(f"상태: **{status_icons.get(ex['status'], ex['status'])}** | 문항수: {len(ex['questions'])}개")
                        
                        with ec2:
                            # 'ready' 상태일 때 시작 버튼 활성화
                            if ex['status'] == 'ready':
                                if st.button("▶️ 시험 시작", key=f"btn_start_{ex['id']}", use_container_width=True):
                                    update_exam_status(ex['id'], 'active')
                                    st.success("시험을 시작했습니다! 학생이 응시할 수 있습니다.")
                                    st.rerun()
                            # 'active' 상태일 때 종료 버튼 활성화
                            elif ex['status'] == 'active':
                                if st.button("⏹️ 시험 종료", key=f"btn_stop_{ex['id']}", use_container_width=True):
                                    update_exam_status(ex['id'], 'closed')
                                    st.warning("시험을 종료했습니다! 더 이상 학생이 답안을 제출할 수 없습니다.")
                                    st.rerun()
                            else:
                                st.write("")
                                
                        with ec3:
                            if ex['status'] == 'active':
                                st.caption("학생들이 로그인하면 이 시험지가 즉시 노출됩니다.")
                            elif ex['status'] == 'closed':
                                st.caption("시험이 만료되어 추가 응시가 차단되었습니다.")
                            else:
                                st.caption("시작 버튼을 누르면 시험이 개방됩니다.")
            else:
                st.info("개설된 시험지가 존재하지 않습니다.")

            st.markdown("---")
            # 🌟 [개선] 과정별, 과목별, 개인별 종합 성적 일람표 (Pandas 테이블 상세 구현)
            st.subheader("📊 3. 수강생 종합 성적표 및 AI 평가 분석")
            all_submissions = get_all_submissions()
            
            if all_submissions:
                df_subs = pd.DataFrame(all_submissions)
                
                # 표 표시용 컬럼 추출 및 이름 한글화
                df_display = df_subs[["course_name", "subject_name", "student_name", "score", "created_at"]].rename(columns={
                    "course_name": "교육과정명",
                    "subject_name": "과목/평가명",
                    "student_name": "수강생명",
                    "score": "점수",
                    "created_at": "응시시간"
                })

                # 상단 필터 셀렉트박스
                f_col1, f_col2, f_col3 = st.columns(3)
                with f_col1:
                    filter_course = st.selectbox("교육과정 필터", ["전체"] + list(df_display["교육과정명"].unique()))
                with f_col2:
                    filter_subject = st.selectbox("과목 필터", ["전체"] + list(df_display["과목/평가명"].unique()))
                with f_col3:
                    filter_student = st.selectbox("수강생 필터", ["전체"] + list(df_display["수강생명"].unique()))
                
                # 필터 연산 적용
                filtered_df = df_display.copy()
                if filter_course != "전체":
                    filtered_df = filtered_df[filtered_df["교육과정명"] == filter_course]
                if filter_subject != "전체":
                    filtered_df = filtered_df[filtered_df["과목/평가명"] == filter_subject]
                if filter_student != "전체":
                    filtered_df = filtered_df[filtered_df["수강생명"] == filter_student]

                # 필터된 정형 데이터프레임 표 출력
                st.dataframe(filtered_df, use_container_width=True, hide_index=True)
                
                # 시각화 통계 바차트
                st.markdown("##### 📈 필터 결과 수강생 성적 분포 그래프")
                if not filtered_df.empty:
                    st.bar_chart(filtered_df.set_index("수강생명")["점수"], use_container_width=True)
                else:
                    st.info("조회할 성적 데이터가 없습니다.")

                # 만약 특정 수강생의 채점지 상세보기가 선택되어 있다면 노출
                if st.session_state.view_submission_detail is not None:
                    detail_sub = st.session_state.view_submission_detail
                    exam_info = get_exam_by_id(detail_sub["exam_id"])
                    
                    with st.container(border=True):
                        st.markdown(f"### 🔍 **{detail_sub['student_name']}** 학생의 **{detail_sub['subject_name']}** 채점지 상세 보기")
                        if st.button("❌ 상세 채점표 닫기", key="btn_close_detail_view"):
                            st.session_state.view_submission_detail = None
                            st.rerun()
                        
                        if exam_info:
                            render_detailed_scorecard(exam_info["questions"], detail_sub["answers"], detail_sub["ai_feedback"])
                        else:
                            st.error("오류: 해당 시험 문항 정보를 불러올 수 없습니다.")
                    st.markdown("---")

                # 개별 학생 피드백 피드 조회
                st.markdown("##### 💡 학생별 AI 개별 채점 보고서 피드")
                for sub in all_submissions:
                    # 필터 조건 적용에 맞춰 카드 노출 결정
                    if (filter_course == "전체" or sub["course_name"] == filter_course) and \
                       (filter_subject == "전체" or sub["subject_name"] == filter_subject) and \
                       (filter_student == "전체" or sub["student_name"] == filter_student):
                        with st.expander(f"👤 {sub['student_name']} - [{sub['subject_name']}] 점수: {sub['score']}점"):
                            st.caption(f"제출일시: {sub['created_at']}")
                            
                            # 상세 채점표 보기 버튼
                            if st.button("🔍 채점지 상세 보기", key=f"btn_show_detail_{sub['id']}"):
                                st.session_state.view_submission_detail = sub
                                st.rerun()
                                
                            try:
                                import json
                                fb_parsed = json.loads(sub['ai_feedback'])
                                st.markdown(f"**AI 총평**: {fb_parsed.get('overall_comment', '')}")
                            except Exception:
                                st.markdown(sub['ai_feedback'])
            else:
                st.info("제출된 시험 데이터가 존재하지 않습니다.")

    # --- 우측 영역: Real-time Status Monitor ---
    with col_status:
        st.title("📊 Real-time Dashboard")
        st.markdown("교육 현황 및 공지 히스토리 실시간 현황")
        st.markdown("---")

        # 1. 최근 생성 공지사항 피드
        st.subheader("📢 최근 생성 공지 피드")
        try:
            announcements = get_all_announcements()
            if announcements:
                for ann in announcements[:4]: 
                    with st.container(border=True):
                        st.markdown(f"🔔 **{ann['title']}**")
                        st.caption(f"🕒 작성시간: {ann['created_at']}")
                        content_preview = ann['content'] if len(ann['content']) < 150 else ann['content'][:150] + "..."
                        st.markdown(content_preview)
            else:
                st.info("작성된 공지사항 이력이 없습니다.")
        except Exception as e:
            st.error(f"공지 피드 로드 오류: {e}")

        st.markdown("---")

        # 2. 최근 상담 이력 요약 타임라인
        st.subheader("💬 학생 상담 이력 요약")
        try:
            students = get_all_students()
            sorted_students = sorted(students, key=lambda x: x['last_consult_date'] or '', reverse=True)
            
            has_consults = False
            for std in sorted_students:
                if std['consulting_notes']:
                    has_consults = True
                    with st.container(border=True):
                        st.markdown(f"👤 **{std['name']}** ({std['career_goal']})")
                        st.caption(f"🗓️ 최종 상담일: {std['last_consult_date']} | 출결: {std['attendance']}/20회 | 과제: {std['assignment_score']}점")
                        st.markdown(std['consulting_notes'])
            
            if not has_consults:
                st.info("등록된 학생 상담 이력이 없습니다.")
        except Exception as e:
            st.error(f"상담 이력 로드 오류: {e}")

# ---------------------------------------------
# 3. 학생 평가 포털 및 제어 연동 (Student Portal)
# ---------------------------------------------
else:
    st.title("📝 학생 온라인 평가 센터")
    st.markdown(f"수강생 **{st.session_state.username}** 님, 환영합니다! 현재 시행 중인 평가 시험에 성실히 응시해 주시기 바랍니다.")
    st.markdown("---")
    
    # 🌟 [개선] 현재 'active' 상태인 시험만 로드
    active_exams = get_active_exams()
    
    if active_exams:
        selected_ex = st.selectbox(
            "응시할 활성 시험지를 선택하세요:", 
            active_exams, 
            format_func=lambda x: f"[{x['course_name']}] {x['subject_name']}"
        )
        
        if selected_ex:
            # 🌟 [개선] 해당 학생이 이미 제출했는지 중복 검증
            already_submitted = has_student_submitted(selected_ex["id"], st.session_state.username)
            
            if already_submitted:
                st.warning("⚠️ 이미 해당 시험지에 대한 답안 제출이 완료되었습니다. 중복 제출 및 재응시는 불가합니다.")
                # 학생의 이전 제출 이력 조회하여 상세 보기 출력
                all_subs = get_exam_submissions(selected_ex["id"])
                my_sub = next((s for s in all_subs if s["student_name"] == st.session_state.username), None)
                if my_sub:
                    st.info("👇 수강생님의 채점 및 상세 피드백 결과입니다.")
                    render_detailed_scorecard(selected_ex["questions"], my_sub["answers"], my_sub["ai_feedback"])
            else:
                st.success(f"🟢 **응시 가능 시험**: {selected_ex['subject_name']} (교육과정: {selected_ex['course_name']})")
                
                questions = selected_ex["questions"]
                student_answers = []
                
                with st.form("student_exam_taking_form"):
                    st.markdown("### 📝 평가 문제 및 답안 작성")
                    st.write("")
                    
                    for q in questions:
                        q_num = q["number"]
                        q_type = q["type"]
                        
                        st.markdown(f"**Q{q_num}. {q['question']}**")
                        
                        if q_type == "choice":
                            choice_ans = st.radio(
                                "정답을 선택하세요:", 
                                q["options"], 
                                index=0, 
                                key=f"student_choice_{selected_ex['id']}_{q_num}"
                            )
                            student_answers.append({"number": q_num, "answer": choice_ans[0]})
                        else:
                            text_ans = st.text_area(
                                "답안을 작성하세요:", 
                                placeholder="정답 및 핵심 소스코드를 이곳에 상세히 기술해 주세요.",
                                key=f"student_text_{selected_ex['id']}_{q_num}"
                            )
                            student_answers.append({"number": q_num, "answer": text_ans})
                        
                        st.markdown("---")
                        
                    submit_btn = st.form_submit_button("✍️ 최종 답안 및 시험지 전송")
                    
                if submit_btn:
                    # 🌟 제출 직전 마지막 확인용 중복 검증 실행 (동시성 락 예방)
                    if has_student_submitted(selected_ex["id"], st.session_state.username):
                        st.error("이미 제출 완료된 상태입니다. 중복 제출할 수 없습니다.")
                    else:
                        with st.spinner("AI 채점위원(grading_agent)이 제출 답안지 키워드 매칭 및 코드 완성도를 채점 중입니다..."):
                            score, feedback_md = asyncio.run(grade_exam_submission_async(questions, student_answers))
                            # DB 등록
                            insert_submission(selected_ex["id"], st.session_state.username, student_answers, score, feedback_md)
                        
                        st.balloons()
                        st.success(f"🎉 시험 제출이 성공적으로 처리되었습니다! 획득 점수: {score}점")
                        
                        with st.container(border=True):
                            st.markdown(f"### 👤 {st.session_state.username} 학생 채점 평가 결과")
                            render_detailed_scorecard(questions, student_answers, feedback_md)
                        
                        # 응시 상태 즉시 재갱신 유도
                        st.rerun()
    else:
        st.info("💡 현재 진행 중(시험 시작 선언)인 활성 시험지가 없습니다. 강사님의 시험 시작 지시가 있을 때까지 잠시 대기해 주세요.")
