import json
import re
import asyncio
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

# 각 서브 에이전트 가져오기
from agents.lecture_agent import query_lecture_async
from agents.student_agent import query_student_async
from agents.schedule_agent import query_schedule_async
from agents.notice_agent import generate_notice_async
from agents.assignment_agent import review_assignment_async
from agents.course_agent import handle_course_query

load_dotenv()

SUPERVISOR_SYSTEM_PROMPT = """당신은 교육 행정 보조 시스템의 관제 콘솔이자 중앙 오케스트레이터인 Supervisor Agent입니다.
사용자의 질문(자연어)을 분석하여 적절한 서브 에이전트들을 호출하는 실행 계획(Plan)을 JSON 형식으로 작성해야 합니다.

[사용 가능한 서브 에이전트]
1. `lecture_agent`: 교재, 핵심 개념(HTML, CSS, JS, React, Python 등), NCS 평가 기준 등 강의 자료에 대한 RAG 검색이 필요할 때 사용.
2. `student_agent`: 학생 이름, 성적, 출결, 상담 내용, 진로 등 학생 개인 정보 조회가 필요할 때 사용.
3. `schedule_agent`: 주차별 강의 주제, 과제 마감 기한, 시험 일정 등 학사 스케줄 조회가 필요할 때 사용.
4. `assignment_agent`: 학생이 작성한 소스코드에 대한 설명, 오류 분석, 안티패턴 탐지, 성능 개선 및 리팩토링 피드백이 필요할 때 사용.
5. `notice_agent`: 알림톡이나 LMS에 게시할 공지문(안내문) 작성을 요청할 때 사용. 이전 단계의 조회 결과를 본문 재료(컨텍스트)로 쓸 수 있음.
6. `course_agent`: 새로운 교육과정 개설, 커리큘럼 설계, 강의안 작성, 과목 시험문제 출제 등 강의 자료 저작에 대한 요청이 있을 때 사용.

[실행 계획 JSON 포맷 규칙]
반드시 다음 구조의 JSON만 출력해야 하며, 추가 설명이나 마크다운 백틱(```json)은 생략해 주세요.

{{
  "direct_answer": "서브 에이전트 조회 없이 단순 인사('안녕', '반가워'), 소개 등 직접 답변이 가능한 문장. 서브 에이전트 호출이 필요한 경우 null로 설정합니다.",
  "steps": [
    {{
      "step_id": 1,
      "agent": "student_agent", // 'student_agent' | 'schedule_agent' | 'lecture_agent' | 'assignment_agent' | 'notice_agent'
      "query": "에이전트에 전달할 개별 질의어 또는 코드 텍스트 (예: '김민수 상담 내용 조회')",
      "depends_on_steps": [] // 이 단계가 실행되기 전에 완료되어야 하는 이전 step_id 목록. 없으면 빈 리스트 [].
    }},
    {{
      "step_id": 2,
      "agent": "notice_agent",
      "query": "공지사항 작성을 위한 강사의 구체적인 지시 사항 (예: '김민수 상담 내용과 일정 정보를 취합하여 학부모 공지 작성')",
      "depends_on_steps": [1] // 1단계의 실행 결과가 이 단계의 context_str로 제공되어야 함을 의미
    }}
  ]
}}

[태스크 분해 및 비동기 처리 가이드]
- 만약 사용자가 복합 요청을 했다면(예: '김민수 상담 내용과 다음 주 학사 일정을 조회해서 학부모 안내 공지 써줘'):
  1단계: student_agent 호출 (김민수 상담 내용 조회) - depends_on_steps: []
  2단계: schedule_agent 호출 (다음 주 학사 일정 조회) - depends_on_steps: []
  3단계: notice_agent 호출 (공지문 작성) - depends_on_steps: [1, 2]
  - 이 경우, 1단계와 2단계는 병렬 실행이 가능합니다.
- 단순 요청(예: '김민수 출결 조회해줘')인 경우, 하나의 step만 steps 배열에 넣습니다.
- 코드 리뷰 요청(예: '이 코드 분석해줘: function foo() {{ ... }}')인 경우, code 부분 전체를 query 필드에 넣고 agent를 `assignment_agent`로 설정합니다.
"""

async def run_supervisor_workflow(user_message: str) -> str:
    """
    Supervisor Agent 실행 및 서브 에이전트 오케스트레이션 워크플로우
    """
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

    # 1. 실행 계획 생성
    prompt = ChatPromptTemplate.from_messages([
        ("system", SUPERVISOR_SYSTEM_PROMPT),
        ("human", "사용자 질의: {message}")
    ])

    response = await llm.ainvoke(prompt.format(message=user_message))
    response_text = response.content.strip()

    # 백틱 기호 정제 (경우에 따라 LLM이 마크다운 블록을 추가로 감싸는 것 방지)
    response_text = re.sub(r"^```json\s*", "", response_text)
    response_text = re.sub(r"\s*```$", "", response_text)

    try:
        plan = json.loads(response_text)
    except Exception as e:
        print(f"JSON Parsing Error: {e}\nRaw Response: {response_text}")
        return "죄송합니다. 사용자의 질문에서 분석 계획을 수립하는 도중 오류가 발생했습니다."

    # 직접 답변 처리
    if plan.get("direct_answer"):
        return plan["direct_answer"]

    steps = plan.get("steps", [])
    if not steps:
        return "수행할 작업 계획을 생성하지 못했습니다. 질문을 다시 한번 명확히 작성해 주세요."

    # 실행 과정 관리 딕셔너리
    step_results = {}
    step_tasks = {} # step_id -> asyncio.Task

    # 각 에이전트 비동기 호출 매핑
    async def execute_step(step):
        step_id = step["step_id"]
        agent_name = step["agent"]
        query = step["query"]
        depends = step.get("depends_on_steps", [])

        # 의존성이 있는 단계들의 실행이 완료될 때까지 기다림
        if depends:
            dep_tasks = [step_tasks[dep_id] for dep_id in depends if dep_id in step_tasks]
            if dep_tasks:
                await asyncio.gather(*dep_tasks)

        # 의존성 결과들을 취합하여 컨텍스트로 변환 (notice_agent 같은 곳에 주입)
        context_parts = []
        for dep_id in depends:
            dep_res = step_results.get(dep_id, "")
            context_parts.append(f"[이전 단계 {dep_id} 결과]:\n{dep_res}")
        context_str = "\n\n".join(context_parts)

        # 서브 에이전트 비동기 실행
        try:
            print(f"[Supervisor] Executing Step {step_id} with Agent: {agent_name}...")
            if agent_name == "lecture_agent":
                res = await query_lecture_async(query)
            elif agent_name == "student_agent":
                res = await query_student_async(query)
            elif agent_name == "schedule_agent":
                res = await query_schedule_async(query)
            elif agent_name == "assignment_agent":
                res = await review_assignment_async(query)
            elif agent_name == "course_agent":
                res = await handle_course_query(query)
            elif agent_name == "notice_agent":
                # 공지 작성을 위해 컨텍스트 정보 전달
                notice_res = await generate_notice_async(instruction=query, context_str=context_str)
                res = f"### [제목] {notice_res['title']}\n\n{notice_res['content']}"
            else:
                res = f"알 수 없는 에이전트 '{agent_name}'가 지정되었습니다."
        except Exception as e:
            res = f"에이전트 {agent_name} 실행 중 오류 발생: {e}"

        step_results[step_id] = res
        return res

    # 의존성에 따라 Topological 정렬 방식으로 실행하기 위해, 루프를 돌며 비동기 Task 예약
    # 여기서는 간단하게 의존관계가 순서대로 정의되었다고 가정하고 순차 분석하되,
    # asyncio.create_task를 통해 독립적인 작업들은 알아서 백그라운드 병렬 처리되도록 합니다.
    for step in steps:
        step_id = step["step_id"]
        # loop.create_task or asyncio.create_task
        task = asyncio.create_task(execute_step(step))
        step_tasks[step_id] = task

    # 모든 작업 완료 대기
    await asyncio.gather(*step_tasks.values())

    # 최종 결과 종합 보고서 생성
    if len(steps) == 1:
        # 단일 태스크인 경우 깔끔하게 해당 결과만 반환
        return step_results[steps[0]["step_id"]]
    else:
        # 복합 태스크인 경우 각 단계별 결과를 마크다운 리포트로 합성
        report = "## 🛠️ 교육 보조 멀티 에이전트 복합 처리 결과\n\n"
        for step in steps:
            step_id = step["step_id"]
            agent_name = step["agent"]
            query = step["query"]
            
            # 한글 이름 매핑
            agent_ko = {
                "student_agent": "학생 관리 에이전트 (SQL)",
                "schedule_agent": "학사 일정 에이전트 (SQL)",
                "lecture_agent": "강의 자료 RAG 에이전트",
                "assignment_agent": "코드 리뷰 에이전트",
                "notice_agent": "공지 자동 작성 에이전트",
                "course_agent": "교육 설계 에이전트 (Creator)"
            }.get(agent_name, agent_name)

            report += f"### 📍 단계 {step_id}: {agent_ko}\n"
            report += f"* **수행 태스크**: {query}\n"
            report += f"{step_results[step_id]}\n\n"
            report += "---\n\n"
            
        report += "**[종합 안내]** 요청하신 복합 태스크가 비동기 병렬 협업을 통해 모두 완료되었습니다."
        return report

if __name__ == "__main__":
    # 단위 테스트 코드 (복합 질의 처리 검증)
    async def test():
        complex_query = "김민수 출결 상태 확인하고 다음 주 평가 일정 포함해서 학부모 안내용 공지문 하나 써줘"
        print(f"Testing Query: {complex_query}")
        result = await run_supervisor_workflow(complex_query)
        print("\n[Supervisor Final Report]:\n")
        print(result)

    asyncio.run(test())
