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

import datetime

def calculate_end_date(start_date, total_hours, daily_hours, course_type, holiday_dates=None):
    """
    시작일, 전체 수업 시간, 하루 수업 시간, 과정 구분(평일/주말), 제외일(공휴일/공강일)을
    고려하여 실제 과정이 완료되는 날짜(종료일)를 계산합니다.
    """
    if not total_hours or not daily_hours or total_hours <= 0 or daily_hours <= 0:
        return start_date, 0
    
    # 제외일 세트 구성
    excluded = set()
    if holiday_dates:
        for d in holiday_dates:
            if isinstance(d, dict):
                # date 또는 제외 날짜 속성 추출
                d_val = d.get("date") or d.get("제외 날짜")
                if not d_val:
                    continue
                d = d_val
                
            if isinstance(d, (datetime.date, datetime.datetime)):
                excluded.add(d)
            elif isinstance(d, str) and d.strip():
                try:
                    excluded.add(datetime.datetime.strptime(d.strip(), "%Y-%m-%d").date())
                except ValueError:
                    pass

    days_needed = (total_hours + daily_hours - 1) // daily_hours
    current_date = start_date
    days_counted = 0
    
    while days_counted < days_needed:
        is_weekend = current_date.weekday() in (5, 6) # 5: Saturday, 6: Sunday
        
        # 제외 조건 체크
        is_holiday = current_date in excluded
        
        is_class_day = False
        if course_type == "평일과정":
            if not is_weekend and not is_holiday:
                is_class_day = True
        elif course_type == "주말과정":
            if is_weekend and not is_holiday:
                is_class_day = True
        else: # 예외적인 경우
            if not is_holiday:
                is_class_day = True
                
        if is_class_day:
            days_counted += 1
            
        if days_counted < days_needed:
            current_date += datetime.timedelta(days=1)
            
    return current_date, days_needed

def get_korean_holidays():
    """
    2026년부터 2030년까지 대한민국의 주요 법정 공휴일, 대체공휴일 및 근로자의 날 매핑 사전입니다.
    """
    return {
        # 2026년
        "2026-01-01": "신정",
        "2026-02-16": "설날 연휴",
        "2026-02-17": "설날",
        "2026-02-18": "설날 연휴",
        "2026-03-01": "삼일절",
        "2026-03-02": "대체공휴일 (삼일절)",
        "2026-05-01": "근로자의 날",
        "2026-05-05": "어린이날",
        "2026-05-24": "부처님오신날",
        "2026-05-25": "대체공휴일 (부처님오신날)",
        "2026-06-03": "지방선거일",
        "2026-06-06": "현충일",
        "2026-08-15": "광복절",
        "2026-08-17": "대체공휴일 (광복절)",
        "2026-09-24": "추석 연휴",
        "2026-09-25": "추석",
        "2026-09-26": "추석 연휴",
        "2026-09-28": "대체공휴일 (추석)",
        "2026-10-03": "개천절",
        "2026-10-05": "대체공휴일 (개천절)",
        "2026-10-09": "한글날",
        "2026-12-25": "성탄절",
        
        # 2027년
        "2027-01-01": "신정",
        "2027-02-06": "설날 연휴",
        "2027-02-07": "설날",
        "2027-02-08": "설날 연휴",
        "2027-02-09": "대체공휴일 (설날)",
        "2027-03-01": "삼일절",
        "2027-05-01": "근로자의 날",
        "2027-05-05": "어린이날",
        "2027-05-13": "부처님오신날",
        "2027-06-06": "현충일",
        "2027-06-07": "대체공휴일 (현충일)",
        "2027-07-17": "제헌절",
        "2027-07-19": "대체공휴일 (제헌절)",
        "2027-08-15": "광복절",
        "2027-08-16": "대체공휴일 (광복절)",
        "2027-09-14": "추석 연휴",
        "2027-09-15": "추석",
        "2027-09-16": "추석 연휴",
        "2027-10-03": "개천절",
        "2027-10-04": "대체공휴일 (개천절)",
        "2027-10-09": "한글날",
        "2027-10-11": "대체공휴일 (한글날)",
        "2027-12-25": "성탄절",
        "2027-12-27": "대체공휴일 (성탄절)",
        
        # 2028년
        "2028-01-01": "신정",
        "2028-01-26": "설날 연휴",
        "2028-01-27": "설날",
        "2028-01-28": "설날 연휴",
        "2028-03-01": "삼일절",
        "2028-04-12": "국회의원 선거일",
        "2028-05-01": "근로자의 날",
        "2028-05-02": "부처님오신날",
        "2028-05-05": "어린이날",
        "2028-06-06": "현충일",
        "2028-08-15": "광복절",
        "2028-10-02": "추석 연휴",
        "2028-10-03": "추석 / 개천절",
        "2028-10-04": "추석 연휴",
        "2028-10-05": "대체공휴일",
        "2028-10-09": "한글날",
        "2028-12-25": "성탄절",
        
        # 2029년
        "2029-01-01": "신정",
        "2029-02-12": "설날 연휴",
        "2029-02-13": "설날",
        "2029-02-14": "설날 연휴",
        "2029-03-01": "삼일절",
        "2029-05-01": "근로자의 날",
        "2029-05-05": "어린이날",
        "2029-05-07": "대체공휴일 (어린이날)",
        "2029-05-20": "부처님오신날",
        "2029-05-21": "대체공휴일 (부처님오신날)",
        "2029-06-06": "현충일",
        "2029-08-15": "광복절",
        "2029-09-21": "추석 연휴",
        "2029-09-22": "추석",
        "2029-09-23": "추석 연휴",
        "2029-09-24": "대체공휴일 (추석)",
        "2029-10-03": "개천절",
        "2029-10-09": "한글날",
        "2029-12-25": "성탄절",
        
        # 2030년
        "2030-01-01": "신정",
        "2030-02-02": "설날 연휴",
        "2030-02-03": "설날",
        "2030-02-04": "설날 연휴",
        "2030-02-05": "대체공휴일 (설날)",
        "2030-03-01": "삼일절",
        "2030-05-01": "근로자의 날",
        "2030-05-05": "어린이날",
        "2030-05-06": "대체공휴일 (어린이날)",
        "2030-05-09": "부처님오신날",
        "2030-06-06": "현충일",
        "2030-08-15": "광복절",
        "2030-09-11": "추석 연휴",
        "2030-09-12": "추석",
        "2030-09-13": "추석 연휴",
        "2030-10-03": "개천절",
        "2030-10-09": "한글날",
        "2030-12-25": "성탄절"
    }

def sync_holidays(start_date, total_hours, daily_hours, course_type):
    """
    설정 변경 시 예상 강의 기간 내의 국경일을 자동으로 찾아 기존의 사용자 지정 공강일과 통합합니다.
    """
    if not total_hours or not daily_hours or total_hours <= 0 or daily_hours <= 0:
        return
        
    # 대략적인 수업일 계산 (휴일 없을 때의 기준일수 * 3배 범위 스캔)
    days_est = (total_hours + daily_hours - 1) // daily_hours
    limit_date = start_date + datetime.timedelta(days=days_est * 3)
    
    # 국경일 조회
    holidays_dict = get_korean_holidays()
    national_holidays = []
    curr = start_date
    while curr <= limit_date:
        date_str = curr.strftime("%Y-%m-%d")
        if date_str in holidays_dict:
            national_holidays.append((curr, holidays_dict[date_str]))
        curr += datetime.timedelta(days=1)
        
    national_dates_set = {h[0] for h in national_holidays}
    
    # 현재 세션 상태 데이터 추출
    current_df = st.session_state.temp_holidays
    manual_rows = []
    for idx, row in current_df.iterrows():
        d = row["제외 날짜"]
        if pd.isna(d):
            continue
        if isinstance(d, datetime.datetime):
            d = d.date()
        elif isinstance(d, str):
            try:
                d = datetime.datetime.strptime(d.strip(), "%Y-%m-%d").date()
            except ValueError:
                continue
                
        # 새 국경일 범위에 포함되지 않는 날짜만 사용자 지정 공강일로 유지
        if d not in national_dates_set:
            manual_rows.append({"제외 날짜": d, "비고": row.get("비고") or "학원 공강일"})
            
    # 국경일과 수동 입력 공강일 병합
    combined = []
    for d, name in national_holidays:
        combined.append({"제외 날짜": d, "비고": name})
    combined.extend(manual_rows)
    
    # 날짜 순으로 정렬
    combined.sort(key=lambda x: x["제외 날짜"])
    
    # 세션 상태 갱신
    st.session_state.temp_holidays = pd.DataFrame(combined, columns=["제외 날짜", "비고"])

# Streamlit 페이지 기본 설정
st.set_page_config(
    page_title="EduPilot Agent - 강사의 두 번째 뇌",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Tailwind CSS v3 CDN 로드 및 기본 스타일 설정
st.markdown("""
<script src="https://cdn.tailwindcss.com"></script>
<style>
    /* Streamlit 기본 사이드바와 헤더 완전 차단 */
    [data-testid="stSidebar"] {
        display: none !important;
    }
    [data-testid="stHeader"] {
        background-color: transparent !important;
        pointer-events: none !important; /* 투명 헤더가 마우스 클릭 차단하는 것 완전 방지 */
    }
    /* 밝은 테마 기본 배경색 및 전체 가독성을 위한 검정색 텍스트 강제 */
    .stApp {
        background-color: #f8fafc !important;
        color: #0f172a !important;
    }
    /* 일반 마크다운 글자색을 어둡게 처리하여 시인성 확보 */
    .stMarkdown, .stMarkdown p, .stMarkdown li, .stMarkdown span, .stMarkdown label {
        color: #1e293b !important;
    }
    /* 타이틀/헤더 글자색 검정색 변경 */
    h1, h2, h3, h4, h5, h6 {
        color: #0f172a !important;
    }
    /* Streamlit 기본 탭 스타일 조정 및 전체 컨테이너 패딩 조절 */
    .main .block-container {
        padding-top: 110px !important;
        padding-bottom: 80px !important;
    }
</style>
""", unsafe_allow_html=True)

# 세션 상태 초기화 (로그인 상태)
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.role = None      # 'teacher' or 'student'
    st.session_state.username = None  # '교사' 또는 학생 이름

if "current_tab" not in st.session_state:
    st.session_state.current_tab = "chatbot" # "chatbot", "course", "exam"

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

if "temp_holidays" not in st.session_state:
    st.session_state.temp_holidays = pd.DataFrame(columns=["제외 날짜", "비고"])


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
    # 로그인 화면 전용 스타일 주입 (밝은 테마)
    st.markdown("""
    <style>
        /* 로그인 배경 및 레이아웃 재지정 - 밝은 톤 */
        .stApp {
            background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%) !important;
        }
        
        /* 로그인 카드 테두리 및 그림자 효과 - 밝은 백그라운드 */
        div[data-testid="stVerticalBlockBorderWrapper"] {
            background-color: rgba(255, 255, 255, 0.9) !important;
            backdrop-filter: blur(16px) !important;
            border: 1px solid rgba(226, 232, 240, 0.8) !important;
            border-radius: 20px !important;
            padding: 2.5rem !important;
            box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.05), 0 10px 10px -5px rgba(0, 0, 0, 0.03) !important;
        }
        
        /* 데스크탑형(DT) 화면에서 로그인 박스 최소 너비 420px 고정 */
        @media (min-width: 768px) {
            div[data-testid="stVerticalBlockBorderWrapper"] {
                min-width: 420px !important;
                width: 420px !important;
                margin: 0 auto !important;
            }
        }
        
        /* 텍스트 입력 필드 */
        div[data-testid="stTextInput"] label {
            color: #334155 !important; /* slate-700 */
            font-weight: 600 !important;
            font-size: 13px !important;
        }
        div[data-testid="stTextInput"] input {
            background-color: #ffffff !important;
            color: #0f172a !important; /* 검정색 계열 */
            border: 1px solid #cbd5e1 !important; /* slate-300 */
            border-radius: 10px !important;
            padding: 10px 14px !important;
            transition: all 0.3s ease;
        }
        div[data-testid="stTextInput"] input:focus {
            border-color: #4f46e5 !important; /* indigo-600 */
            box-shadow: 0 0 0 2px rgba(79, 70, 229, 0.15) !important;
        }
        
        /* 로그인 실행 버튼 */
        div[data-testid="stBaseButton-secondary"] button {
            background: linear-gradient(135deg, #4f46e5 0%, #6366f1 100%) !important;
            color: white !important;
            border: none !important;
            border-radius: 10px !important;
            padding: 12px 20px !important;
            font-size: 15px !important;
            font-weight: 600 !important;
            box-shadow: 0 4px 14px 0 rgba(99, 102, 241, 0.3) !important;
            transition: all 0.2s ease !important;
            margin-top: 10px !important;
        }
        div[data-testid="stBaseButton-secondary"] button:hover {
            transform: translateY(-1px) !important;
            box-shadow: 0 6px 20px 0 rgba(99, 102, 241, 0.4) !important;
        }
    </style>
    
    <script>
        // 패스워드 입력란에서 Enter 감지 시 로그인 버튼 클릭 처리
        const loginInterval = setInterval(() => {
            const passwordField = document.querySelector('input[type="password"]');
            const loginBtn = Array.from(document.querySelectorAll('button')).find(
                btn => btn.textContent.includes('로그인 실행')
            );
            
            if (passwordField && loginBtn) {
                if (!passwordField.classList.contains('enter-event-bound')) {
                    passwordField.classList.add('enter-event-bound');
                    passwordField.addEventListener('keydown', function(e) {
                        if (e.keyCode === 13 || e.key === 'Enter') {
                            e.preventDefault();
                            loginBtn.click();
                        }
                    });
                }
            }
        }, 400);
    </script>
    """, unsafe_allow_html=True)
    
    st.markdown("<br><br>", unsafe_allow_html=True)
    l_col1, l_col2, l_col3 = st.columns([1, 1.3, 1])
    
    with l_col2:
        with st.container(border=True):
            st.markdown("""
            <div class="text-center flex flex-col items-center py-4" style="text-align: center;">
                <div class="w-24 h-24 bg-gradient-to-tr from-indigo-600 to-purple-600 rounded-3xl flex items-center justify-center text-5xl shadow-lg shadow-indigo-600/20 mb-6" style="font-size: 150px; text-align: center; line-height: 70px">
                    🤖
                </div>
                <h1 class="text-3xl font-black text-slate-800 tracking-tight" style="line-height: .7; font-size: 2.2rem;margin-left:24px;">
                    EduPilot Platform
                </h1>
                <p class="text-sm text-slate-500 mt-1">지능형 교육 정보 플랫폼 로그인</p>
                <div class="text-xs text-indigo-700 bg-indigo-50 border border-indigo-100 rounded-lg py-3 px-4 mt-6 w-full text-center font-medium">
                    📢 강사 및 학생 인증 후 서비스를<br> 이용하실 수 있습니다.
                </div>
            </div>
            """, unsafe_allow_html=True)
            st.markdown("<div class='h-2'></div>", unsafe_allow_html=True)
            
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
                    st.session_state.current_tab = "chatbot"
                    st.success("✔️ 교사(강사) 계정으로 인증되었습니다. 포털로 진입합니다.")
                    st.rerun()
                else:
                    # 학생 정보 DB 조회 검증
                    student_db_info = get_student_info(login_id)
                    if student_db_info:
                        st.session_state.logged_in = True
                        st.session_state.role = "student"
                        st.session_state.username = login_id
                        st.session_state.current_tab = "student_exam"
                        st.success(f"✔️ {login_id} 학생으로 인증되었습니다. 시험 포털로 진입합니다.")
                        st.rerun()
                    else:
                        st.error("❌ 등록되지 않은 학생 이름입니다. 강사 대시보드에 학생 정보가 등록되어 있는지 확인해 주세요.")
    st.stop() # 로그인이 완료될 때까지 아래 본문 렌더링 중지

# ---------------------------------------------
# 1. 사이드바 구성 (환영 표시 및 로그아웃 + 권한 격리)
# ---------------------------------------------
# ---------------------------------------------
# 1. 상단 고정 네비게이션 바 (Navbar) 렌더링 및 스타일 정의
# ---------------------------------------------
role_ko = "교사/강사" if st.session_state.role == "teacher" else "수강생"

# 상단 Navbar 고정용 트리거 마크다운 주입
st.markdown('<div class="nav-bg-trigger"></div>', unsafe_allow_html=True)

# 탭 전환용 st.columns 렌더링 (첫 번째 stHorizontalBlock을 CSS로 fixed 배치하고 1200px 중앙 정렬)
st.markdown("""
<style>
    /* 조상 컨테이너들의 CSS transform/perspective/will-change 강제 해제 (fixed 붕괴의 근본적 원인 제거) */
    .stApp, .stAppViewContainer, .stAppMainContent, .main, .block-container, [data-testid="stVerticalBlock"], [data-testid="stVerticalBlockBorderWrapper"], .element-container {
        transform: none !important;
        perspective: none !important;
        will-change: auto !important;
    }

    /* 네비게이션 탭이 포함된 stHorizontalBlock을 핀포인트 타겟팅하여 viewport 상단에 고정 */
    div[data-testid="stHorizontalBlock"]:has(.st-key-btn_nav_chat),
    div[data-testid="stHorizontalBlock"]:has(.st-key-btn_nav_logout),
    div[data-testid="stHorizontalBlock"]:has(.st-key-btn_nav_student_logout) {
        position: fixed !important;
        top: 0px !important; /* 화면 최상단 밀착 */
        left: 50% !important;
        white-space: nowrap !important;
        transform: translateX(-50%) !important; /* 가로 중앙 정렬 */
        width: 1019px !important;
        max-width: 1019px !important;
        z-index: 999999 !important; /* 최상위 레이어로 절대적인 레이어링 보장 */
        height: 80px !important;
        display: flex !important;
        align-items: center !important;
        background-color: transparent !important;
        margin: 0 auto !important;
        padding: 0 1.5rem !important;
    }
    
    /* 가상 요소로 100vw 전체 폭의 흰색 Navbar 배경 삽입 (네비게이션 행에 철석 결합됨) */
    div[data-testid="stHorizontalBlock"]:has(.st-key-btn_nav_chat)::before,
    div[data-testid="stHorizontalBlock"]:has(.st-key-btn_nav_logout)::before,
    div[data-testid="stHorizontalBlock"]:has(.st-key-btn_nav_student_logout)::before {
        content: "" !important;
        position: fixed !important;
        top: 0 !important;
        left: 50% !important;
        transform: translateX(-50%) !important;
        width: 100vw !important; /* 브라우저 가로 전체 폭 */
        height: 80px !important;
        background-color: #ffffff !important;
        border-bottom: 1px solid #e2e8f0 !important;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.02) !important;
        z-index: -1 !important; /* 버튼들 뒤로 배경 위치 */
    }
    
    /* stHorizontalBlock 내부의 컬럼 컨테이너 정렬 강제 */
    div[data-testid="stHorizontalBlock"]:has(.st-key-btn_nav_chat) > div,
    div[data-testid="stHorizontalBlock"]:has(.st-key-btn_nav_logout) > div,
    div[data-testid="stHorizontalBlock"]:has(.st-key-btn_nav_student_logout) > div {
        display: flex !important;
        align-items: center !important;
        /* height: 109px !important; */
        padding-top: 10px !important;
    }
    
    /* 특정 컬럼 및 공통 stColumn의 flex 너비 제어 (유연한 레이아웃 확장 보장) */
    div[data-testid="stHorizontalBlock"]:has(.st-key-btn_nav_chat) div[data-testid="stColumn"],
    div[data-testid="stHorizontalBlock"]:has(.st-key-btn_nav_student_logout) div[data-testid="stColumn"] {
        flex: 1 1 auto !important;
        width: auto !important;
    }

    /* st-emotion-cache-jko06q 클래스의 flex 속성 커스텀 지정 */
    .st-emotion-cache-jko06q {
        flex: 1 1 calc(14.1667% - 1rem) !important;
    }
    
    /* 탭 및 로그아웃 버튼 스타일 */
    div[data-testid="stHorizontalBlock"]:has(.st-key-btn_nav_chat) button,
    div[data-testid="stHorizontalBlock"]:has(.st-key-btn_nav_student_logout) button {
        height: 36px !important;
        width: auto !important; /* 가로 크기를 자동으로 맞춤 */
        min-width: max-content !important; /* 글자 크기만큼 100% 영역 확보 */
        white-space: nowrap !important; /* 줄바꿈 방지 */
        padding-left: 14px !important;
        padding-right: 14px !important;
        background-color: #f1f5f9 !important; /* slate-100 */
        color: #475569 !important; /* slate-600 */
        border: 1px solid #e2e8f0 !important;
        border-radius: 8px !important;
        font-size: 13px !important;
        font-weight: 700 !important;
        transition: all 0.2s ease;
    }
    
    /* 버튼 내부의 모든 span/p 자식 요소들도 줄바꿈 및 넘침 방지 */
    div[data-testid="stHorizontalBlock"]:has(.st-key-btn_nav_chat) button *,
    div[data-testid="stHorizontalBlock"]:has(.st-key-btn_nav_student_logout) button * {
        white-space: nowrap !important;
        width: auto !important;
        display: inline-block !important;
    }
    div[data-testid="stHorizontalBlock"]:has(.st-key-btn_nav_chat) button:hover,
    div[data-testid="stHorizontalBlock"]:has(.st-key-btn_nav_student_logout) button:hover {
        background-color: #e2e8f0 !important;
        color: #0f172a !important;
        border-color: #cbd5e1 !important;
    }
    /* primary (활성 탭) 스타일 */
    div[data-testid="stHorizontalBlock"]:has(.st-key-btn_nav_chat) button[data-baseweb="button"][class*="primary"] {
        background: #4f46e5 !important;
        color: white !important;
        border: none !important;
        box-shadow: 0 4px 6px -1px rgba(79, 70, 229, 0.2) !important;
    }
    
    /* 로그아웃 버튼 스타일 (마지막 컬럼 내 버튼) */
    div[data-testid="stHorizontalBlock"]:has(.st-key-btn_nav_chat) div[data-testid="column"]:last-child button,
    div[data-testid="stHorizontalBlock"]:has(.st-key-btn_nav_student_logout) div[data-testid="column"]:last-child button {
        background-color: #ef4444 !important;
        color: white !important;
        border: none !important;
    }
    div[data-testid="stHorizontalBlock"]:has(.st-key-btn_nav_chat) div[data-testid="column"]:last-child button:hover,
    div[data-testid="stHorizontalBlock"]:has(.st-key-btn_nav_student_logout) div[data-testid="column"]:last-child button:hover {
        background-color: #dc2626 !important;
    }
</style>
""", unsafe_allow_html=True)

# 실제 네비게이션 버튼들 정의 (교사와 학생 다르게 배치하여 HTML 영역과 조화)
if st.session_state.role == "teacher":
    nav_cols = st.columns([2.6, 1.4, 2.0, 1.7, 3.3, 1.0])
    with nav_cols[0]:
        st.markdown(f"""<div class="flex items-center gap-3" style="display:flex; flex-direction: row;gap: 10px;align-items: center;">
            <span class="text-3xl leading-none" style="font-size: 70px; line-height: 0.9;">🤖</span>
            <div class="flex flex-col">
                <span class="text-base font-black text-slate-800 leading-none">EduPilot Agent</span>
            </div>
            <span class="text-[9px] bg-indigo-50 text-indigo-600 border border-indigo-200 px-2 py-0.5 rounded-full font-black leading-none">{role_ko}</span>
        </div>""", unsafe_allow_html=True)
    with nav_cols[1]:
        is_chat = (st.session_state.current_tab == "chatbot")
        if st.button("🤖 에이전트 챗봇", key="btn_nav_chat", type="primary" if is_chat else "secondary", use_container_width=True):
            st.session_state.current_tab = "chatbot"
            st.rerun()
    with nav_cols[2]:
        is_course = (st.session_state.current_tab == "course")
        if st.button("🆕 교육과정 & 강의 설계", key="btn_nav_course", type="primary" if is_course else "secondary", use_container_width=True):
            st.session_state.current_tab = "course"
            st.rerun()
    with nav_cols[3]:
        is_exam = (st.session_state.current_tab == "exam")
        if st.button("📊 시험 및 평가 관리", key="btn_nav_exam", type="primary" if is_exam else "secondary", use_container_width=True):
            st.session_state.current_tab = "exam"
            st.rerun()
    with nav_cols[4]:
        st.markdown(f"""<div class="flex items-center justify-end w-full pr-4">
            <span class="text-xs text-slate-600 font-bold">👤 <span class="text-slate-900 font-black text-sm">{st.session_state.username}</span> 님 환영합니다!</span>
        </div>""", unsafe_allow_html=True)
    with nav_cols[5]:
        if st.button("🚪 로그아웃", key="btn_nav_logout", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.role = None
            st.session_state.username = None
            st.session_state.messages = [
                {"role": "assistant", "content": "안녕하세요! 교육 운영 보조 멀티 에이전트 **EduPilot Agent**입니다. 무엇을 도와드릴까요?"}
            ]
            st.rerun()
else:
    # 학생 화면용 네비게이션
    nav_cols = st.columns([3.5, 7.5, 1.0])
    with nav_cols[0]:
        st.markdown(f"""<div class="flex items-center gap-3" style="display:flex; flex-direction: row;gap: 10px;align-items: center;">
            <span class="text-3xl leading-none" style="font-size: 55px">🤖</span>
            <div class="flex flex-col">
                <span class="text-base font-black text-slate-800 leading-none">EduPilot Agent</span>
            </div>
            <span class="text-[9px] bg-indigo-50 text-indigo-600 border border-indigo-200 px-2 py-0.5 rounded-full font-black leading-none">{role_ko}</span>
        </div>""", unsafe_allow_html=True)
    with nav_cols[1]:
        st.markdown(f"""<div class="flex items-center justify-end w-full pr-4">
            <span class="text-xs text-slate-600 font-bold">👤 <span class="text-slate-900 font-black text-sm">{st.session_state.username}</span> 님 환영합니다!</span>
        </div>""", unsafe_allow_html=True)
    with nav_cols[2]:
        if st.button("🚪 로그아웃", key="btn_nav_student_logout", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.role = None
            st.session_state.username = None
            st.session_state.messages = [
                {"role": "assistant", "content": "안녕하세요! 교육 운영 보조 멀티 에이전트 **EduPilot Agent**입니다. 무엇을 도와드릴까요?"}
            ]
            st.rerun()

# ---------------------------------------------
# 2. 강사 업무 포털 (Teacher Portal)
# ---------------------------------------------
if st.session_state.role == "teacher":
    # 0. 시스템 관리 및 강의 자료 업로드 배너 (사이드바 대체형 가로 배너)
    st.markdown("""
    <div class="bg-white border border-slate-200 rounded-xl p-4 mb-6 shadow-sm">
        <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
                <span class="text-xl">🛠️</span>
                <span class="text-sm font-bold text-slate-800">시스템 관리 및 강의 문서 업로드 제어판</span>
            </div>
            <span class="text-[10px] text-indigo-600 bg-indigo-50 border border-indigo-100 px-2 py-0.5 rounded-full font-semibold">배너 제어판</span>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    with st.expander("🛠️ 시스템 관리 및 강의 문서 업로드 제어판 열기", expanded=False):
        b_col1, b_col2, b_col3 = st.columns([1, 1.2, 1.2])
        with b_col1:
            st.subheader("🗄️DB관리")
            if st.button("🔄 DB 초기화 및 더미 데이터 적재", key="banner_reset_db", use_container_width=True):
                with st.spinner("DB 초기화 중..."):
                    init_db(force_reset=True)
                st.success("DB가 완벽히 초기화되었습니다!")
                st.rerun()
        with b_col2:
            st.subheader("📚 강의자료 PDF업로드")
            uploaded_files = st.file_uploader(
                "추가 교재 문서를 업로드해 주세요.",
                type=["pdf"],
                accept_multiple_files=True,
                key="banner_file_uploader"
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
        with b_col3:
            st.subheader("📡 강의자료현황")
            from agents.lecture_agent import find_all_pdfs, DOCS_DIR
            try:
                pdfs = find_all_pdfs(DOCS_DIR)
                display_pdfs = [os.path.basename(p) for p in pdfs if os.path.basename(p) != "edupilot_project_proposal.pdf"]
                st.write(f"현재 로드된 PDF 파일 수: **{len(display_pdfs)}**개")
                pdf_list_html = "".join([f"<div style='margin-bottom: 6px; font-size: 13px; color: #64748b; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;'>• {filename}</div>" for filename in display_pdfs])
                st.markdown(f"""
                    <div style="
                        max-height: 95px; 
                        overflow-y: auto; 
                        border: 1px solid #e2e8f0; 
                        padding: 8px 12px; 
                        border-radius: 8px; 
                        background-color: #f8fafc;
                    ">
                        {pdf_list_html}
                    </div>
                """, unsafe_allow_html=True)
            except:
                st.caption("PDF 없음")

    col_chat, col_status = st.columns([2, 1], gap="medium")

    with col_chat:
        # --- 탭 1: 에이전트 챗봇 ---
        if st.session_state.current_tab == "chatbot":
            st.markdown("""
            <div class="mb-4">
                <h2 class="text-2xl font-extrabold text-slate-800 flex items-center gap-2">
                    <span style="font-size: 50px">🤖</span> EduPilot Agent
                </h2>
                <p class="text-xs text-slate-500 mt-1">자연어로 질문하면 하단 6가지 전문 에이전트가 협업해 최적의 교안과 리포트를 설계합니다.</p>
            </div>
            """, unsafe_allow_html=True)
            
            # 챗 인풋을 화면 하단에 고정하는 CSS 주입
            st.markdown("""
            <style>
                /* st.chat_input 위치 고정 및 디자인 */
                div[data-testid="stChatInput"] {
                    position: fixed !important;
                    bottom: 24px !important;
                    left: calc(33% - 40px) !important; /* 좌측 col_chat 영역 중앙에 배치하기 위함 */
                    width: 42% !important;
                    max-width: 700px !important;
                    z-index: 999 !important;
                    background-color: #ffffff !important; /* 화이트 */
                    border: 1px solid #cbd5e1 !important; /* 연한 보더 */
                    border-radius: 12px !important;
                    box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.08) !important;
                }
                div[data-testid="stChatInput"] textarea {
                    color: #0f172a !important;
                }
            </style>
            """, unsafe_allow_html=True)
            
            with st.container(border=True):
                f_col1, f_col2, f_col3 = st.columns(3)
                with f_col1:
                    st.markdown("📚 **Lecture RAG**:  \n교재 PDF 정밀 출처 검색")
                    st.markdown("🗄️ **Student SQL**:  \n학생 출결/상담 DB 조회")
                with f_col2:
                    st.markdown("💻 **Assignment**:  \n소스코드 결함/리팩토링 분석")
                    st.markdown("📅 **Schedule**:  \n과제 마감 및 학사일정 조회")
                with f_col3:
                    st.markdown("📢 **Notice**:  \n수집 정보 통합 공지문 완성")
                    st.markdown("🏫 **Course**:  \n커리큘럼/강의안/시험 자동 저작")

            st.markdown("---")
            for msg in st.session_state.messages:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])

            # 하단 고정 영역 가림 방지 패딩
            st.markdown("<div style='height: 80px;'></div>", unsafe_allow_html=True)

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
        elif st.session_state.current_tab == "course":
            st.subheader("🏫 1. 신규 교육과정 개설 & 커리큘럼 설계")
            new_course_name = st.text_input("과정 이름 입력", placeholder="예: FastAPI 파이썬 웹 백엔드 실무 과정")
            new_course_desc = st.text_area("과정 개요 및 설명", placeholder="예: 파이썬을 기반으로 FastAPI와 SQLite DB를 활용한 백엔드 구축 교육")
            
            c_col1, c_col2 = st.columns(2)
            with c_col1:
                total_hours = st.number_input("전체 수업 시간 (시간)", min_value=1, value=80, step=1)
                start_date = st.date_input("과정 시작일", value=datetime.date.today())
            with c_col2:
                course_type = st.selectbox("과정 구분", ["평일과정", "주말과정"], index=0)
                daily_hours = st.number_input("하루 수업 시간 (시간)", min_value=1, max_value=24, value=8, step=1)

            # 설정값 변경 감지 및 공휴일 동기화 트리거
            current_settings = (start_date, int(total_hours), int(daily_hours), course_type)
            if "prev_course_settings" not in st.session_state:
                st.session_state.prev_course_settings = current_settings
                sync_holidays(start_date, int(total_hours), int(daily_hours), course_type)
            elif st.session_state.prev_course_settings != current_settings:
                st.session_state.prev_course_settings = current_settings
                sync_holidays(start_date, int(total_hours), int(daily_hours), course_type)

            st.markdown("**📅 제외일 등록 (공휴일/임시공휴일/학원 공강일 등)**")
            edited_df = st.data_editor(
                st.session_state.temp_holidays,
                num_rows="dynamic",
                column_config={
                    "제외 날짜": st.column_config.DateColumn(
                        "제외할 날짜 선택",
                        min_value=datetime.date(2026, 1, 1),
                        max_value=datetime.date(2030, 12, 31),
                        format="YYYY-MM-DD",
                        required=True
                    ),
                    "비고": st.column_config.TextColumn(
                        "비고 (휴무 사유)",
                        default="학원 공강일"
                    )
                },
                use_container_width=True,
                key="holidays_editor"
            )
            
            # 실시간 종료일 및 기간 정보 계산 (종료일 필터링 전 최초 계산)
            holiday_list = []
            if edited_df is not None and not edited_df.empty:
                for idx, row in edited_df.iterrows():
                    d = row["제외 날짜"]
                    if pd.isna(d):
                        continue
                    if isinstance(d, datetime.datetime):
                        d = d.date()
                    elif isinstance(d, str) and d.strip():
                        try:
                            d = datetime.datetime.strptime(d.strip(), "%Y-%m-%d").date()
                        except ValueError:
                            continue
                    holiday_list.append(d)
                
            end_date, days_needed = calculate_end_date(start_date, total_hours, daily_hours, course_type, holiday_list)
            
            # 종료일 이후의 공휴일/공강일 필터링 (공휴일 체크 한계값을 종료일로 설정)
            filtered_rows = []
            holiday_structured_list = []
            if edited_df is not None and not edited_df.empty:
                for idx, row in edited_df.iterrows():
                    d = row["제외 날짜"]
                    if pd.isna(d):
                        continue
                    remark = row.get("비고") or "학원 공강일"
                    if isinstance(d, datetime.datetime):
                        d = d.date()
                    elif isinstance(d, str) and d.strip():
                        try:
                            d = datetime.datetime.strptime(d.strip(), "%Y-%m-%d").date()
                        except ValueError:
                            continue
                    
                    if d <= end_date:
                        filtered_rows.append({"제외 날짜": d, "비고": remark})
                        d_str = d.strftime("%Y-%m-%d")
                        holiday_structured_list.append({"date": d_str, "remark": remark})
            
            # 종료일 이후의 날짜가 있어서 필터링되었다면 세션 상태를 업데이트하고 화면을 다시 그림
            original_valid_count = len(holiday_list)
            if len(filtered_rows) < original_valid_count:
                st.session_state.temp_holidays = pd.DataFrame(filtered_rows, columns=["제외 날짜", "비고"])
                st.rerun()
            elif edited_df is not None:
                # 필터링 대상이 없더라도 현재 에디터 상태를 세션 상태에 저장하여 동기화
                st.session_state.temp_holidays = edited_df
            
            # 주차 수 계산
            if course_type == "평일과정":
                weeks = (days_needed + 4) // 5
            else:  # 주말과정
                weeks = (days_needed + 1) // 2
            if weeks <= 0:
                weeks = 1
                
            st.info(
                f"ℹ️ **실시간 교육 일정 정보**\n"
                f"- **총 수업 일수**: {days_needed}일\n"
                f"- **총 수업 주차**: {weeks}주차\n"
                f"- **예상 종료일**: **{end_date.strftime('%Y-%m-%d')}** (지정된 제외일 및 주말 미수업 반영)"
            )
            
            submit_course = st.button("🆕 과정 등록 및 AI 커리큘럼 생성", type="primary", use_container_width=True)

            if submit_course and new_course_name:
                with st.spinner(f"Course 에이전트가 {weeks}주 커리큘럼을 생성하고 있습니다..."):
                    import json
                    holiday_json = json.dumps(holiday_structured_list, ensure_ascii=False)
                    curr_list = asyncio.run(generate_curriculum_async(new_course_name, new_course_desc, weeks))
                    
                    c_id = insert_course(
                        name=new_course_name,
                        description=new_course_desc,
                        total_hours=int(total_hours),
                        start_date=start_date.strftime("%Y-%m-%d"),
                        end_date=end_date.strftime("%Y-%m-%d"),
                        course_type=course_type,
                        daily_hours=int(daily_hours),
                        holiday_dates=holiday_json
                    )
                    for item in curr_list:
                        insert_curriculum(c_id, item["week"], item["topic"], item["details"])
                st.success(f"교육과정 '{new_course_name}'이 등록되고 {weeks}주 커리큘럼이 구축되었습니다!")
                st.session_state.temp_holidays = pd.DataFrame(columns=["제외 날짜", "비고"])
                if "prev_course_settings" in st.session_state:
                    del st.session_state.prev_course_settings
                st.rerun()

            st.markdown("---")
            st.subheader("📚 2. 개설된 교육과정 조회 및 주차별 강의안 생성")
            courses = get_all_courses()
            if courses:
                for c in courses:
                    with st.expander(f"📖 {c['name']} (과정 ID: {c['id']})"):
                        st.write(f"**과정 개요**: {c['description']}")
                        
                        # 신규 컬럼 세팅 정보 표시
                        if c.get("total_hours") is not None:
                            h_dates_info = []
                            if c.get("holiday_dates"):
                                try:
                                    import json
                                    raw_holidays = json.loads(c["holiday_dates"])
                                    holidays_dict = get_korean_holidays()
                                    for item in raw_holidays:
                                        if isinstance(item, dict):
                                            d_str = item.get("date", "")
                                            remark = item.get("remark", "")
                                            if remark:
                                                h_dates_info.append(f"{d_str} ({remark})")
                                            else:
                                                h_dates_info.append(d_str)
                                        else: # 구버전 호환용 (단순 날짜 문자열)
                                            d_str = str(item)
                                            if d_str in holidays_dict:
                                                h_dates_info.append(f"{d_str} ({holidays_dict[d_str]})")
                                            else:
                                                h_dates_info.append(f"{d_str} (제외일)")
                                except Exception:
                                    pass
                            
                            c_info_col1, c_info_col2 = st.columns(2)
                            with c_info_col1:
                                st.write(f"⏱️ **총 수업 시간**: {c['total_hours']}시간 (하루 {c['daily_hours']}시간)")
                                st.write(f"📅 **교육 기간**: {c['start_date']} ~ {c['end_date']}")
                            with c_info_col2:
                                st.write(f"🏫 **과정 구분**: {c['course_type']}")
                                if h_dates_info:
                                    st.write(f"🚫 **지정 제외일 ({len(h_dates_info)}일)**: {', '.join(h_dates_info)}")
                                else:
                                    st.write("🚫 **지정 제외일**: 없음")
                            st.markdown("---")

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
                        
                        max_w = max([cur["week"] for cur in curr_data]) if curr_data else 8
                        target_week = st.number_input(f"강의안을 작성할 주차 선택 ({c['name']})", min_value=1, max_value=max_w, value=1, key=f"week_inp_{c['id']}")
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
        elif st.session_state.current_tab == "exam":
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
        st.subheader("📊 Real-time Dashboard")
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
    st.markdown(f"""
    <div class="bg-gradient-to-r from-slate-50 via-indigo-50 to-slate-50 border border-slate-200 rounded-2xl p-6 mb-6 shadow-sm">
        <h1 class="text-3xl font-black text-slate-800 tracking-tight flex items-center gap-3">
            📝 학생 온라인 평가 센터
        </h1>
        <p class="text-xs text-slate-600 mt-2">
            수강생 <b class="text-indigo-600 font-bold">{st.session_state.username}</b> 님, 환영합니다! 현재 시행 중인 평가 시험에 성실히 응시해 주시기 바랍니다.
        </p>
        <div class="text-[11px] text-amber-800 bg-amber-50 border border-amber-200 rounded-lg py-2.5 px-3 mt-4 w-full font-medium">
            💡 <b>안내 사항</b>: 강사님이 출제하고 <b>[시험 시작]</b>을 선언한 활성 평가 시험지만 아래에 나타납니다. 평가를 성실히 수행하시고 답안을 전송하면 중복 제출 방지를 위해 시험지가 자동으로 마감처리됩니다.
        </div>
    </div>
    """, unsafe_allow_html=True)
    
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
