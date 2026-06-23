import os
import sqlite3
import asyncio
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from database import DB_PATH

load_dotenv()

# SQL 생성을 위한 시스템 프롬프트
SQL_SYSTEM_PROMPT = """당신은 SQLite 데이터베이스 조회용 SQL 쿼리를 작성하는 전문 SQL 생성기입니다.
주어진 데이터베이스의 테이블 스키마와 사용자의 요청을 기반으로, SQLite3에 적합한 SELECT 쿼리문만을 작성하세요.
답변에는 마크다운 코드 블록이나 추가 설명 없이, 오직 하나의 SQL 쿼리문만 반환해야 합니다.

[테이블 구조]
students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL, -- 학생 이름 (예: '김민수', '이영희' 등)
    attendance INTEGER DEFAULT 0, -- 출결 횟수 (총 20회 만점)
    assignment_score INTEGER DEFAULT 0, -- 과제 점수 (100점 만점)
    consulting_notes TEXT, -- 상담 일지 및 내용 요약
    career_goal TEXT, -- 희망 진로/목표 (예: '프론트엔드 개발자', '풀스택 개발자', '백엔드 개발자', 'UI/UX 엔지니어', '미정')
    last_consult_date TEXT -- 최종 상담 일자 (YYYY-MM-DD)
)

[예시 질문 및 생성 쿼리]
- 질문: "김민수 출결 상태 보여줘"
  쿼리: SELECT name, attendance FROM students WHERE name LIKE '%김민수%'
- 질문: "취업 준비 중인 학생 누구야?"
  쿼리: SELECT name, career_goal FROM students WHERE career_goal != '미정' AND career_goal IS NOT NULL
- 질문: "김민수 상담 내용 보여줘"
  쿼리: SELECT name, consulting_notes, last_consult_date FROM students WHERE name LIKE '%김민수%'
- 질문: "과제 성적이 우수한 학생 순서대로 보여줘"
  쿼리: SELECT name, assignment_score FROM students ORDER BY assignment_score DESC

[주의사항]
- 쿼리는 반드시 SELECT로만 시작해야 하며, 데이터베이스를 수정하는 INSERT/UPDATE/DELETE/DROP 등은 절대 허용하지 않습니다.
- 사용자의 질문에 부합하는 컬럼만 선택하여 조회하도록 작성해 주세요.
- 코드 블록 기호(예: ```sql ... ```)는 절대 사용하지 말고, 오직 쿼리 텍스트만 출력하세요.
"""

# 결과를 바탕으로 한국어 답변을 구성하기 위한 시스템 프롬프트
FORMAT_SYSTEM_PROMPT = """당신은 교육생 관리 데이터를 바탕으로 교사에게 자연어로 보고하는 Student Agent입니다.
제시된 SQL 쿼리 결과(데이터베이스 데이터)를 기반으로 사용자의 질문에 대한 친절하고 세부적인 답변을 한국어 존댓말로 작성해 주세요.
데이터베이스에 없는 추측성 정보는 절대로 추가하지 말고, 있는 사실만 요약해서 제공하세요.
답변 마지막에 '[출처: student.db]' 문구를 반드시 삽입해 주세요.
"""

async def query_student_async(query_str: str) -> str:
    """
    자연어로 들어온 학생 관련 질의를 SQL로 변환하여 SQLite DB를 조회한 후,
    결과 데이터를 자연어 문장으로 답변을 구성하여 반환합니다.
    """
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

    # 1. 자연어 -> SQL 변환
    sql_prompt = ChatPromptTemplate.from_messages([
        ("system", SQL_SYSTEM_PROMPT),
        ("human", "질문: {query}")
    ])
    
    sql_chain = sql_prompt | llm
    sql_response = await llm.ainvoke(sql_prompt.format(query=query_str))
    sql_query = sql_response.content.strip()

    # 안전성 필터링 (SELECT 이외의 쿼리 차단)
    if not sql_query.upper().startswith("SELECT"):
        return "보안상 안전하지 않거나 비정상적인 데이터베이스 조회 요청입니다."

    print(f"[Generated SQL]: {sql_query}")

    # 2. SQLite 쿼리 실행
    # DB 파일이 없는 경우, database.py의 초기화 기능이 선행되어야 함
    if not os.path.exists(DB_PATH):
        return "데이터베이스가 존재하지 않습니다. 먼저 DB 초기화를 진행해 주세요."

    try:
        # 블로킹 작업이므로 스레드 풀에서 DB 쿼리 실행
        def run_db_query():
            conn = sqlite3.connect(DB_PATH)
            # 딕셔너리 형태로 결과 컬럼 접근 가능하게 함
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(sql_query)
            rows = cursor.fetchall()
            # 컬럼명 리스트 추출
            colnames = [description[0] for description in cursor.description] if cursor.description else []
            conn.close()
            # 직렬화 가능한 딕셔너리 목록으로 변환
            return [dict(r) for r in rows], colnames

        db_results, colnames = await asyncio.to_thread(run_db_query)
    except Exception as e:
        return f"데이터베이스 쿼리 실행 중 오류가 발생했습니다: {e}\n[실행하려던 쿼리]: {sql_query}"

    if not db_results:
        return f"요청하신 조건에 부합하는 학생 데이터를 찾지 못했습니다.\n[출처: student.db]"

    # 3. 조회 결과 데이터를 한국어 문장으로 구성
    format_prompt = ChatPromptTemplate.from_messages([
        ("system", FORMAT_SYSTEM_PROMPT),
        ("human", "질문: {query}\n실행한 SQL: {sql}\n조회 데이터: {data}")
    ])

    formatted_data_str = "\n".join([str(dict(r)) for r in db_results])
    
    response = await llm.ainvoke(format_prompt.format(
        query=query_str,
        sql=sql_query,
        data=formatted_data_str
    ))

    return response.content

if __name__ == "__main__":
    # 단위 테스트 코드
    async def test():
        res = await query_student_async("김민수 출결이랑 과제 점수 요약해줘")
        print("\n[Result]:")
        print(res)
        
    asyncio.run(test())
