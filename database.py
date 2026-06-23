import os
import sqlite3
import json
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "edupilot.db")

def get_connection():
    """SQLite 데이터베이스 연결을 생성합니다."""
    return sqlite3.connect(DB_PATH)

def init_db(force_reset=False):
    """
    데이터베이스 스키마를 초기화하고 필요한 경우 더미 데이터를 적재합니다.
    """
    if force_reset and os.path.exists(DB_PATH):
        try:
            os.remove(DB_PATH)
        except Exception as e:
            print(f"Error removing existing database file: {e}")

    conn = get_connection()
    cursor = conn.cursor()

    # 1. 기존 테이블 (students, schedules, announcements)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        attendance INTEGER DEFAULT 0,
        assignment_score INTEGER DEFAULT 0,
        consulting_notes TEXT,
        career_goal TEXT,
        last_consult_date TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS schedules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        week INTEGER NOT NULL,
        topic TEXT NOT NULL,
        assignment_due TEXT,
        exam_date TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS announcements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at TEXT DEFAULT (datetime('now', 'localtime'))
    )
    """)

    # 2. 신규 확장 테이블 (courses, curriculums, lecture_plans, exams, exam_submissions)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS courses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        total_hours INTEGER,
        start_date TEXT,
        end_date TEXT,
        course_type TEXT,
        daily_hours INTEGER,
        holiday_dates TEXT
    )
    """)

    # 기존 DB 테이블 컬럼 마이그레이션 (컬럼 존재하지 않을 시 ALTER TABLE)
    cursor.execute("PRAGMA table_info(courses)")
    cols = [col[1] for col in cursor.fetchall()]
    new_cols = {
        "total_hours": "INTEGER",
        "start_date": "TEXT",
        "end_date": "TEXT",
        "course_type": "TEXT",
        "daily_hours": "INTEGER",
        "holiday_dates": "TEXT"
    }
    for col_name, col_type in new_cols.items():
        if col_name not in cols:
            cursor.execute(f"ALTER TABLE courses ADD COLUMN {col_name} {col_type}")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS curriculums (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_id INTEGER,
        week INTEGER NOT NULL,
        topic TEXT NOT NULL,
        details TEXT,
        FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS lecture_plans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_id INTEGER,
        subject_name TEXT NOT NULL,
        plan_content TEXT,
        FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS exams (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_id INTEGER,
        subject_name TEXT NOT NULL,
        questions_json TEXT, -- JSON 포맷 (문제 배열)
        status TEXT DEFAULT 'ready', -- 'ready' (대기), 'active' (시행중), 'closed' (종료)
        FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS exam_submissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        exam_id INTEGER,
        student_name TEXT NOT NULL,
        answers_json TEXT, -- 학생 제출 답안 JSON
        score INTEGER,
        ai_feedback TEXT,
        created_at TEXT DEFAULT (datetime('now', 'localtime')),
        FOREIGN KEY(exam_id) REFERENCES exams(id) ON DELETE CASCADE
    )
    """)

    conn.commit()

    # 더미 데이터 삽입 (학생 데이터 기준으로 전체 비어 있을 때만 작동)
    cursor.execute("SELECT COUNT(*) FROM students")
    if cursor.fetchone()[0] == 0:
        seed_data(conn)

    conn.close()

def seed_data(conn):
    """데이터베이스에 고품질 데모 데이터를 삽입합니다."""
    cursor = conn.cursor()

    # (기존) 학생 더미 데이터
    students = [
        ("김민수", 18, 92, "React 기초 역량 우수하나 비동기 처리(useEffect, Fetch) 부분 추가 학습 필요. 프론트엔드 개발 부문 취업 희망.", "프론트엔드 개발자", "2026-06-15"),
        ("이영희", 20, 95, "전반적인 프로그래밍 논리 우수. 풀스택 개발자 지망생으로 프로젝트 완수 의지가 매우 높음.", "풀스택 개발자", "2026-06-18"),
        ("박철수", 15, 78, "최근 결석 및 출결이 다소 저조하여 면담 진행함. 백엔드(Python/Django) 프레임워크 학습 및 인프라 구성에 관심.", "백엔드 개발자", "2026-06-10"),
        ("최민지", 19, 88, "UI/UX 디자인 감각이 뛰어나며 React 웹 앱 연동 구현 학습 진행 중. 프론트엔드 또는 퍼블리셔 지망.", "UI/UX 엔지니어", "2026-06-20"),
        ("홍길동", 12, 60, "기초 파이썬 및 프로그래밍 개념 이해도가 낮아 보강 수업 연계 필요. 향후 진로에 대한 고민이 많아 주기적 상담 요망.", "미정", "2026-06-12")
    ]
    cursor.executemany("""
    INSERT INTO students (name, attendance, assignment_score, consulting_notes, career_goal, last_consult_date)
    VALUES (?, ?, ?, ?, ?, ?)
    """, students)

    # (기존) 학사 일정 더미 데이터
    schedules = [
        (1, "HTML/CSS 웹 개발 기초", "HTML 자기소개 페이지 제출 (완료)", "N/A"),
        (2, "JavaScript 기초 문법 및 DOM 조작", "ToDo App 구현 (완료)", "N/A"),
        (3, "JS 비동기 프로그래밍 및 Fetch API", "날씨 API 연동 웹페이지 제출", "1차 필기 평가 (완료)"),
        (4, "React 핵심 개념 (State, Props, useEffect)", "React 쇼핑몰 카트 구현", "N/A"),
        (5, "React Router & Context API 상태 관리", "React 멀티 페이지 블로그 만들기", "N/A"),
        (6, "Python 기초 문법 및 알고리즘 자료구조", "파이썬 알고리즘 풀이 5제 제출", "N/A"),
        (7, "SQL 및 SQLite 데이터베이스 설계", "데이터베이스 모델링 다이어그램 제출", "2차 실기 평가 (대기)"),
        (8, "최종 포트폴리오 프로젝트 완료", "최종 프로젝트 결과물 및 발표 문서 제출", "N/A")
    ]
    cursor.executemany("""
    INSERT INTO schedules (week, topic, assignment_due, exam_date)
    VALUES (?, ?, ?, ?)
    """, schedules)

    # (기존) 공지사항 더미 데이터
    announcements = [
        ("1차 필기 평가 결과 공지", "지난 주 진행된 1차 필기 평가 채점 결과가 완료되었습니다. 학생별 상세 점수는 개별 상담 시 전달 예정이며, 전체 평균 점수는 85점입니다. 모두 수고하셨습니다.", "2026-06-16 10:00:00"),
        ("React 쇼핑몰 카트 과제 제출 안내", "이번 주 과제인 'React 쇼핑몰 카트 구현' 제출 기한은 일요일(2026-06-28) 23:59까지입니다. 기한을 꼭 엄수해 주시기 바랍니다.", "2026-06-22 09:00:00")
    ]
    cursor.executemany("""
    INSERT INTO announcements (title, content, created_at)
    VALUES (?, ?, ?)
    """, announcements)

    # (신규) 교육과정 시드
    cursor.execute("""
    INSERT INTO courses (name, description)
    VALUES (?, ?)
    """, ("React 풀스택 엔지니어 과정", "React 프론트엔드 프레임워크와 Python 백엔드를 아우르는 정예 풀스택 개발자 육성 과정"))
    course_id = cursor.lastrowid

    # (신규) 커리큘럼 시드 (8주차 구성)
    curriculums = [
        (course_id, 1, "HTML5/CSS3 레이아웃 설계", "웹 표준 구조 설계 및 Flexbox/Grid 스타일 시트 실무 적용"),
        (course_id, 2, "JavaScript Core & DOM 조작", "동적 웹페이지 작성을 위한 바닐라 JS 코어 개념 학습 및 DOM 이벤트 제어"),
        (course_id, 3, "비동기 JS & API 데이터 처리", "Promise, Async/Await 패턴을 사용한 Fetch API 연동 및 네트워크 비동기 제어"),
        (course_id, 4, "React State & 컴포넌트 생명주기", "React Hooks(useState, useEffect) 원리 및 컴포넌트 렌더링 최적화"),
        (course_id, 5, "React 라우팅 및 전역 상태 관리", "React Router Dom 활용 페이지 브랜칭 및 Context API 전역 상태 관리 설계"),
        (course_id, 6, "Python 백엔드 개발 입문", "FastAPI/Flask를 사용한 기초 API 서버 개발 및 라우팅 설계"),
        (course_id, 7, "SQL 데이터베이스 & ORM 연동", "SQLite DB 스키마 설계, CRUD SQL 작성 및 SQL Alchemy ORM 활용 실무"),
        (course_id, 8, "최종 풀스택 프로젝트 완수", "프론트엔드와 백엔드를 연동한 배포형 웹 프로젝트 수행 및 발표")
    ]
    cursor.executemany("""
    INSERT INTO curriculums (course_id, week, topic, details)
    VALUES (?, ?, ?, ?)
    """, curriculums)

    # (신규) 과목별 강의안 시드
    plan_content = """# 4주차 React State & 컴포넌트 생명주기 강의안

## 1. 학습 목표
- React Component의 상태 관리 핵심인 `useState` 사용 목적을 이해한다.
- 사이드 이펙트(Side Effects)를 처리하기 위한 `useEffect` 생명주기 연동법을 마스터한다.

## 2. 핵심 요약
- **State**: 컴포넌트 내부에서 변경될 수 있는 유동적인 데이터.
- **useEffect Clean-up**: 컴포넌트가 언마운트되거나 의존성이 바뀌기 전에 호출되어 메모리 누수를 방지함 (타이머 취합, 이벤트 리스너 해제에 필수).
"""
    cursor.execute("""
    INSERT INTO lecture_plans (course_id, subject_name, plan_content)
    VALUES (?, ?, ?)
    """, (course_id, "React Core", plan_content))

    # (신규) 시험문제지 시드 (객관식 3 + 서술형/코딩 2)
    questions = [
        {
            "type": "choice",
            "number": 1,
            "question": "React에서 컴포넌트 내의 유동적인 상태 데이터를 관리하기 위해 사용하는 대표적인 Hook은 무엇인가요?",
            "options": ["1) useEffect", "2) useState", "3) useContext", "4) useRef"],
            "answer": "2"
        },
        {
            "type": "choice",
            "number": 2,
            "question": "useEffect 훅에서 의존성 배열(dependency array)을 빈 배열([])로 설정했을 때의 동작 방식으로 가장 올바른 것은 무엇인가요?",
            "options": [
                "1) 컴포넌트가 매번 렌더링될 때마다 실행된다.",
                "2) 컴포넌트가 마운트될 때 최초 1회만 실행된다.",
                "3) 컴포넌트가 화면에서 사라질(언마운트) 때 최초 1회만 실행된다.",
                "4) 절대 실행되지 않는다."
            ],
            "answer": "2"
        },
        {
            "type": "choice",
            "number": 3,
            "question": "React에서 부모 컴포넌트로부터 자식 컴포넌트로 읽기 전용 데이터를 전달할 때 사용하는 속성명으로 알맞은 것은 무엇인가요?",
            "options": ["1) State", "2) Props", "3) Context", "4) Reducer"],
            "answer": "2"
        },
        {
            "type": "descriptive",
            "number": 4,
            "question": "useEffect 내에서 반환(return)되는 클린업(Cleanup) 함수의 주된 역할과 그것을 사용해야 하는 구체적인 상황을 서술하시오.",
            "keywords": ["메모리 누수", "해제", "정리", "언마운트", "타이머", "이벤트 리스너"],
            "answer_guide": "컴포넌트가 언마운트되거나 다음 이펙트가 실행되기 전에 이전 리소스를 정리(이벤트 리스너 제거, 타이머 중지 등)하여 메모리 누수를 예방하는 역할을 한다."
        },
        {
            "type": "coding",
            "number": 5,
            "question": "React에서 API 서버로부터 데이터를 비동기로 받아와 상태 'data'를 세팅하는 함수 fetchUserData()를 useEffect를 활용해 작성할 때, 올바른 비동기 호출 코드를 구성하시오. (의존성 배열은 빈 배열로 구성)",
            "keywords": ["useEffect", "async", "await", "fetch", "setData", "[]"],
            "answer_guide": "useEffect(() => { const fetchUserData = async () => { const res = await fetch('url'); const result = await res.json(); setData(result); }; fetchUserData(); }, [])"
        }
    ]
    cursor.execute("""
    INSERT INTO exams (course_id, subject_name, questions_json, status)
    VALUES (?, ?, ?, ?)
    """, (course_id, "React Core 평가", json.dumps(questions, ensure_ascii=False), "active")) # 초기 데이터를 시행중(active) 상태로 생성

    # (신규) 학생 답안 더미 제출 시드
    minsu_answers = [
        {"number": 1, "answer": "2"}, 
        {"number": 2, "answer": "2"}, 
        {"number": 3, "answer": "2"}, 
        {"number": 4, "answer": "컴포넌트가 화면에서 사라질 때 실행되어 타이머나 리스너를 해제하고 메모리 누수를 줄여줍니다."}, 
        {"number": 5, "answer": "useEffect(() => { fetch('url').then(res => res.json()).then(data => setData(data)) }, [])"} 
    ]
    cursor.execute("""
    INSERT INTO exam_submissions (exam_id, student_name, answers_json, score, ai_feedback)
    VALUES (?, ?, ?, ?, ?)
    """, (1, "김민수", json.dumps(minsu_answers, ensure_ascii=False), 85, "객관식 3문항은 모두 정답입니다. 4번 문항에서 메모리 누수와 정리 개념을 잘 짚었으며, 5번 문항 역시 비동기 상태 세팅 코드를 잘 구성했습니다. 비동기 처리의 예외 처리(try-catch)를 보강하면 더욱 좋습니다."))

    chulsoo_answers = [
        {"number": 1, "answer": "1"}, 
        {"number": 2, "answer": "2"}, 
        {"number": 3, "answer": "2"}, 
        {"number": 4, "answer": "데이터를 초기화하는 기능입니다."}, 
        {"number": 5, "answer": "fetch('url')"} 
    ]
    cursor.execute("""
    INSERT INTO exam_submissions (exam_id, student_name, answers_json, score, ai_feedback)
    VALUES (?, ?, ?, ?, ?)
    """, (1, "박철수", json.dumps(chulsoo_answers, ensure_ascii=False), 50, "객관식 1번을 오답 처리했습니다. 상태 관리는 useState 훅을 사용해야 합니다. 4번의 클린업 기능 서술과 5번의 비동기 상태 적용 코드가 매우 미흡합니다. 마운트 시의 생명주기와 비동기 상태 변이 코드에 대해 보강 수업이 필요합니다."))

    conn.commit()

# --- 데이터베이스 조작용 API ---

def get_student_info(name):
    """학생 이름으로 학생의 정보를 단건 조회합니다."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM students WHERE name = ?", (name,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            "id": row[0],
            "name": row[1],
            "attendance": row[2],
            "assignment_score": row[3],
            "consulting_notes": row[4],
            "career_goal": row[5],
            "last_consult_date": row[6]
        }
    return None

def get_all_students():
    """전체 학생 목록을 조회합니다."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM students")
    rows = cursor.fetchall()
    conn.close()
    return [{
        "id": r[0], "name": r[1], "attendance": r[2],
        "assignment_score": r[3], "consulting_notes": r[4],
        "career_goal": r[5], "last_consult_date": r[6]
    } for r in rows]

def get_all_courses():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, description, total_hours, start_date, end_date, course_type, daily_hours, holiday_dates FROM courses")
    rows = cursor.fetchall()
    conn.close()
    return [{
        "id": r[0],
        "name": r[1],
        "description": r[2],
        "total_hours": r[3],
        "start_date": r[4],
        "end_date": r[5],
        "course_type": r[6],
        "daily_hours": r[7],
        "holiday_dates": r[8]
    } for r in rows]

def get_course_curriculum(course_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM curriculums WHERE course_id = ? ORDER BY week ASC", (course_id,))
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "course_id": r[1], "week": r[2], "topic": r[3], "details": r[4]} for r in rows]

def get_course_lecture_plans(course_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM lecture_plans WHERE course_id = ?", (course_id,))
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "course_id": r[1], "subject_name": r[2], "plan_content": r[3]} for r in rows]

def get_exam_by_id(exam_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM exams WHERE id = ?", (exam_id,))
    r = cursor.fetchone()
    conn.close()
    if r:
        return {"id": r[0], "course_id": r[1], "subject_name": r[2], "questions": json.loads(r[3]), "status": r[4]}
    return None

def get_all_exams_with_course():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT e.id, e.course_id, c.name, e.subject_name, e.questions_json, e.status
        FROM exams e
        JOIN courses c ON e.course_id = c.id
    """)
    rows = cursor.fetchall()
    conn.close()
    return [{
        "id": r[0], "course_id": r[1], "course_name": r[2],
        "subject_name": r[3], "questions": json.loads(r[4]), "status": r[5]
    } for r in rows]

def get_exam_submissions(exam_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM exam_submissions WHERE exam_id = ? ORDER BY score DESC", (exam_id,))
    rows = cursor.fetchall()
    conn.close()
    return [{
        "id": r[0], "exam_id": r[1], "student_name": r[2],
        "answers": json.loads(r[3]), "score": r[4], "ai_feedback": r[5], "created_at": r[6]
    } for r in rows]

def get_all_submissions():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT s.id, s.exam_id, e.subject_name, c.name, s.student_name, s.answers_json, s.score, s.ai_feedback, s.created_at
        FROM exam_submissions s
        JOIN exams e ON s.exam_id = e.id
        JOIN courses c ON e.course_id = c.id
        ORDER BY s.id DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [{
        "id": r[0], "exam_id": r[1], "subject_name": r[2], "course_name": r[3], "student_name": r[4],
        "answers": json.loads(r[5]), "score": r[6], "ai_feedback": r[7], "created_at": r[8]
    } for r in rows]

def get_all_announcements():
    """전체 공지사항 이력을 역순(최신순)으로 조회합니다."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM announcements ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return [{
        "id": r[0], "title": r[1], "content": r[2], "created_at": r[3]
    } for r in rows]

def insert_announcement(title, content):
    """새로운 공지사항을 생성합니다."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO announcements (title, content) VALUES (?, ?)", (title, content))
    conn.commit()
    conn.close()

def insert_course(name, description, total_hours=None, start_date=None, end_date=None, course_type=None, daily_hours=None, holiday_dates=None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO courses (name, description, total_hours, start_date, end_date, course_type, daily_hours, holiday_dates) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (name, description, total_hours, start_date, end_date, course_type, daily_hours, holiday_dates))
    conn.commit()
    inserted_id = cursor.lastrowid
    conn.close()
    return inserted_id

def insert_curriculum(course_id, week, topic, details):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO curriculums (course_id, week, topic, details) 
        VALUES (?, ?, ?, ?)
    """, (course_id, week, topic, details))
    conn.commit()
    conn.close()

def insert_lecture_plan(course_id, subject_name, plan_content):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO lecture_plans (course_id, subject_name, plan_content) 
        VALUES (?, ?, ?)
    """, (course_id, subject_name, plan_content))
    conn.commit()
    conn.close()

def insert_exam(course_id, subject_name, questions_list):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO exams (course_id, subject_name, questions_json) 
        VALUES (?, ?, ?)
    """, (course_id, subject_name, json.dumps(questions_list, ensure_ascii=False)))
    conn.commit()
    inserted_id = cursor.lastrowid
    conn.close()
    return inserted_id

def insert_submission(exam_id, student_name, answers_list, score, ai_feedback):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO exam_submissions (exam_id, student_name, answers_json, score, ai_feedback) 
        VALUES (?, ?, ?, ?, ?)
    """, (exam_id, student_name, json.dumps(answers_list, ensure_ascii=False), score, ai_feedback))
    conn.commit()
    conn.close()

def update_exam_status(exam_id, status):
    """시험지의 진행 상태를 변경합니다 ('ready', 'active', 'closed')."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE exams SET status = ? WHERE id = ?", (status, exam_id))
    conn.commit()
    conn.close()

def get_active_exams():
    """현재 시행 중('active') 상태인 시험 목록을 조회합니다."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT e.id, e.course_id, c.name, e.subject_name, e.questions_json, e.status
        FROM exams e
        JOIN courses c ON e.course_id = c.id
        WHERE e.status = 'active'
    """)
    rows = cursor.fetchall()
    conn.close()
    return [{
        "id": r[0], "course_id": r[1], "course_name": r[2],
        "subject_name": r[3], "questions": json.loads(r[4]), "status": r[5]
    } for r in rows]

def has_student_submitted(exam_id, student_name):
    """특정 학생이 특정 시험에 이미 답안을 제출했는지 검증합니다."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM exam_submissions WHERE exam_id = ? AND student_name = ?", (exam_id, student_name))
    count = cursor.fetchone()[0]
    conn.close()
    return count > 0

if __name__ == "__main__":
    init_db(force_reset=True)
    print("Database successfully initialized and seeded with course/exam data!")
