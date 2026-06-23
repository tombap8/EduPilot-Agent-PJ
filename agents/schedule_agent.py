import os
import sqlite3
import asyncio
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from database import DB_PATH

load_dotenv()

# SQL 생성을 위한 시스템 프롬프트
SQL_SYSTEM_PROMPT = """당신은 SQLite 데이터베이스의 학사 일정(schedules) 테이블 조회용 SQL 쿼리를 작성하는 전문 SQL 생성기입니다.
주어진 테이블 스키마와 사용자의 요청을 기반으로, SQLite3에 적합한 SELECT 쿼리문만을 작성하세요.
답변에는 마크다운 코드 블록이나 추가 설명 없이, 오직 하나의 SQL 쿼리문만 반환해야 합니다.

[테이블 구조]
schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    week INTEGER NOT NULL, -- 주차 (1, 2, 3...)
    topic TEXT NOT NULL, -- 강의 주제 (예: 'HTML/CSS 웹 개발 기초', 'React 핵심 개념' 등)
    assignment_due TEXT, -- 해당 주차 과제 및 마감 내용 (예: 'React 쇼핑몰 카트 구현', 'N/A' 등)
    exam_date TEXT -- 해당 주차 시험 또는 평가 일정 (예: '1차 필기 평가 (완료)', '2차 실기 평가 (대기)', 'N/A' 등)
)

[예시 질문 및 생성 쿼리]
- 질문: "다음 주 평가 범위가 어떻게 되지?"
  쿼리: SELECT week, topic, exam_date FROM schedules WHERE exam_date != 'N/A' AND exam_date IS NOT NULL
- 질문: "React 과제 마감일이 언제야?"
  쿼리: SELECT week, topic, assignment_due FROM schedules WHERE topic LIKE '%React%' OR assignment_due LIKE '%React%'
- 질문: "전체 학사 일정 다 보여줘"
  쿼리: SELECT week, topic, assignment_due, exam_date FROM schedules ORDER BY week ASC

[주의사항]
- 쿼리는 반드시 SELECT로만 시작해야 하며, 데이터베이스를 수정하는 INSERT/UPDATE/DELETE/DROP 등은 절대 허용하지 않습니다.
- 사용자의 질문에 부합하는 컬럼만 선택하여 조회하도록 작성해 주세요.
- 코드 블록 기호(예: ```sql ... ```)는 절대 사용하지 말고, 오직 쿼리 텍스트만 출력하세요.
"""

# 결과를 바탕으로 한국어 답변을 구성하기 위한 시스템 프롬프트
FORMAT_SYSTEM_PROMPT = """당신은 교육 학사 일정을 바탕으로 교사에게 자연어로 안내하는 Schedule Agent입니다.
제시된 SQL 쿼리 결과(학사 일정 데이터)를 기반으로 사용자의 질문에 대한 친절한 답변을 한국어 존댓말로 작성해 주세요.
데이터베이스에 없는 추측성 일정 정보는 절대 기재하지 마세요.
답변 마지막에 '[출처: schedule.db]' 문구를 반드시 삽입해 주세요.
"""

async def query_schedule_async(query_str: str) -> str:
    """
    자연어로 들어온 학사 일정 질의를 SQL로 변환하여 schedules 테이블을 조회한 후,
    결과 데이터를 자연어 문장으로 구성하여 반환합니다.
    """
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

    # 1. 자연어 -> SQL 변환
    sql_prompt = ChatPromptTemplate.from_messages([
        ("system", SQL_SYSTEM_PROMPT),
        ("human", "질문: {query}")
    ])
    
    sql_response = await llm.ainvoke(sql_prompt.format(query=query_str))
    sql_query = sql_response.content.strip()

    # 안전성 필터링 (SELECT 이외의 쿼리 차단)
    if not sql_query.upper().startswith("SELECT"):
        return "보안상 안전하지 않거나 비정상적인 학사 일정 조회 요청입니다."

    print(f"[Generated Schedule SQL]: {sql_query}")

    # 2. SQLite 쿼리 실행
    if not os.path.exists(DB_PATH):
        return "데이터베이스가 존재하지 않습니다. 먼저 DB 초기화를 진행해 주세요."

    try:
        def run_db_query():
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(sql_query)
            rows = cursor.fetchall()
            conn.close()
            return [dict(r) for r in rows]

        db_results = await asyncio.to_thread(run_db_query)
    except Exception as e:
        return f"데이터베이스 쿼리 실행 중 오류가 발생했습니다: {e}\n[실행하려던 쿼리]: {sql_query}"

    if not db_results:
        return f"요청하신 일정 조건에 맞는 데이터를 찾지 못했습니다.\n[출처: schedule.db]"

    # 3. 조회 결과 데이터를 한국어 문장으로 구성
    format_prompt = ChatPromptTemplate.from_messages([
        ("system", FORMAT_SYSTEM_PROMPT),
        ("human", "질문: {query}\n실행한 SQL: {sql}\n조회 일정 데이터: {data}")
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
        res = await query_schedule_async("React 과제 제출 마감은 언제까지야?")
        print("\n[Result]:")
        print(res)
        
    asyncio.run(test())
