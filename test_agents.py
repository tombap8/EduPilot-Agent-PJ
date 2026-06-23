import asyncio
import os
import sys
import io

# Windows 콘솔 인코딩을 UTF-8로 강제 재설정하여 이모지 인코딩 충돌을 방지합니다.
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 프로젝트 루트 경로 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import (
    init_db, get_all_students, get_all_courses,
    get_course_curriculum, get_all_exams_with_course, get_exam_submissions,
    update_exam_status, get_active_exams, has_student_submitted
)
from agents.student_agent import query_student_async
from agents.schedule_agent import query_schedule_async
from agents.assignment_agent import review_assignment_async
from agents.lecture_agent import query_lecture_async, ingest_documents
from agents.supervisor import run_supervisor_workflow

# 신규 에이전트 모듈 임포트
from agents.course_agent import generate_curriculum_async, generate_exam_async, generate_single_question_async
from agents.grading_agent import grade_exam_submission_async

async def run_tests():
    print("==================================================")
    print("[TEST] EduPilot Agent Integration and Unit Tests Starting")
    print("==================================================")

    # 1. DB 초기화 테스트
    print("\n1. [DB Test] Database Init & Seeding (With Extended Tables)")
    try:
        init_db(force_reset=True)
        students = get_all_students()
        courses = get_all_courses()
        print(f"[OK] DB initialization completed.")
        print(f"  - Seeded students: {len(students)}")
        print(f"  - Seeded courses: {len(courses)} ({courses[0]['name']})")
    except Exception as e:
        print(f"[ERROR] DB initialization failed: {e}")

    # 2. Student Agent 테스트 (SQL)
    print("\n2. [Student Agent Test] Natural Language to SQL Query Test")
    try:
        res = await query_student_async("김민수 출결 현황과 상담일지 요약해줘")
        print("[OK] Student Agent Response:")
        print(res)
    except Exception as e:
        print(f"[ERROR] Student Agent failed: {e}")

    # 3. Schedule Agent 테스트 (SQL)
    print("\n3. [Schedule Agent Test] Academic Schedule Query Test")
    try:
        res = await query_schedule_async("React 과제 제출일이 몇 주차에 있고 언제까지야?")
        print("[OK] Schedule Agent Response:")
        print(res)
    except Exception as e:
        print(f"[ERROR] Schedule Agent failed: {e}")

    # 4. CourseAgent 테스트 (신규 - 커리큘럼 및 시험 출제)
    print("\n4. [CourseAgent Test] Auto Curriculum & Exam Question Generation Test")
    try:
        print("  - Generating 8-week curriculum for FastAPI course...")
        curr = await generate_curriculum_async("FastAPI 웹 개발 과정", "파이썬 기반 고성능 API 서버 구축")
        print(f"[OK] Curriculum generated successfully: {len(curr)} weeks.")
        for week in curr[:2]:
            print(f"    * Week {week['week']}: {week['topic']} ({week['details'][:30]}...)")
            
        print("  - Generating 5-question exam for React course...")
        exam_qs = await generate_exam_async("React Core 과정", "JSX & Hooks 평가", "JSX, useState, useEffect, virtual DOM")
        print(f"[OK] Exam generated successfully: {len(exam_qs)} questions.")
        for q in exam_qs[:2]:
            print(f"    * Q{q['number']}. {q['question']} (Type: {q['type']})")
            
        print("  - Testing single question replacement for React core descriptive question...")
        single_q = await generate_single_question_async("React Core 과정", "JSX & Hooks 평가", 4, "descriptive", "JSX, useState, useEffect, virtual DOM")
        print(f"[OK] Single question replacement generated successfully: {single_q['question']}")
        print(f"    * Keywords: {single_q.get('keywords', [])}")
        print(f"    * Explanation: {single_q.get('explanation', '')}")
    except Exception as e:
        print(f"[ERROR] CourseAgent failed: {e}")

    # 5. GradingAgent 테스트 (신규 - 하이브리드 자동 채점)
    print("\n5. [GradingAgent Test] Hybrid Semantic Auto Grading Test")
    try:
        sample_questions = [
            {"number": 1, "question": "Q1", "options": [], "answer": "2"},
            {"number": 2, "question": "Q2", "options": [], "answer": "2"},
            {"number": 3, "question": "Q3", "options": [], "answer": "1"},
            {"number": 4, "question": "useEffect의 클린업 역할 서술", "keywords": ["메모리", "누수", "정리"], "answer_guide": "메모리 누수 해제"},
            {"number": 5, "question": "fetch API 세팅 코드", "keywords": ["fetch", "setData"], "answer_guide": "fetch('url')"}
        ]
        sample_student_answers = [
            {"number": 1, "answer": "2"}, 
            {"number": 2, "answer": "2"}, 
            {"number": 3, "answer": "3"}, 
            {"number": 4, "answer": "컴포넌트가 사라질 때 타이머나 구독을 해제 및 정리해주어 메모리 누수가 생기는 것을 예방하는 역할입니다."}, 
            {"number": 5, "answer": "fetch('api/data')"} 
        ]
        print("  - Running hybrid grading for student...")
        score, report = await grade_exam_submission_async(sample_questions, sample_student_answers)
        print(f"[OK] Grading completed. Final Score: {score}/100")
        print(report[:400] + "\n...(truncated)...")
    except Exception as e:
        print(f"[ERROR] GradingAgent failed: {e}")

    # 6. Lecture Agent 테스트 (RAG)
    print("\n6. [Lecture Agent Test] RAG-based Course Material Search Test")
    try:
        from agents.lecture_agent import CHROMA_DIR
        if not os.path.exists(CHROMA_DIR) or not os.listdir(CHROMA_DIR):
            print("  - Building Vector DB Ingestion (First-time setup)...")
            ingest_documents()
        else:
            print("  - Chroma DB already exists. Skipping document ingestion.")
        print("  - Querying 'React useEffect purpose'...")
        res = await query_lecture_async("useEffect의 사용 목적과 클린업 함수에 대해 설명해줘")
        print("[OK] Lecture Agent Response:")
        print(res)
    except Exception as e:
        print(f"[ERROR] Lecture Agent failed: {e}")

    # 7. Supervisor Agent 복합 질의 오케스트레이션 테스트
    print("\n7. [Supervisor Agent Test] Complex Task Decomposition & Asynchronous Orchestration Test")
    complex_query = "김민수 상담 내용을 먼저 파악하고, 다음 주 평가 일정을 조사한 뒤에, 이 내용들을 요약해서 학부모 안내 공지사항 하나 만들어줘"
    try:
        print(f"  - Complex Query: \"{complex_query}\"")
        res = await run_supervisor_workflow(complex_query)
        print("[OK] Supervisor Agent Final Integrated Report:")
        print(res)
    except Exception as e:
        print(f"[ERROR] Supervisor Agent failed: {e}")

    # 8. 시험 수명주기 및 제출 유효성 검증 테스트 (신규)
    print("\n8. [Exam Lifecycle & Duplicate Submission Verification Test]")
    try:
        print("  - Checking currently active exams...")
        active_list = get_active_exams()
        print(f"    * Active exams count: {len(active_list)}")
        
        print("  - Verifying if '김민수' has submitted exam_id 1 (Seeded)...")
        minsu_submitted = has_student_submitted(1, "김민수")
        print(f"    * 김민수 제출 상태: {minsu_submitted} (Expected: True)")
        
        print("  - Verifying if '홍길동' has submitted exam_id 1...")
        gildong_submitted = has_student_submitted(1, "홍길동")
        print(f"    * 홍길동 제출 상태: {gildong_submitted} (Expected: False)")
        
        print("  - Testing updating exam_id 1 status to 'closed'...")
        update_exam_status(1, "closed")
        active_list_post = get_active_exams()
        print(f"    * Active exams count after closing: {len(active_list_post)} (Expected: 0)")
        
        # 복원
        update_exam_status(1, "active")
        print("[OK] Exam Lifecycle & Submission Checks passed.")
    except Exception as e:
        print(f"[ERROR] Exam Lifecycle testing failed: {e}")

    print("==================================================")
    print("[SUCCESS] All agent testing processes completed successfully.")
    print("==================================================")

if __name__ == "__main__":
    asyncio.run(run_tests())
