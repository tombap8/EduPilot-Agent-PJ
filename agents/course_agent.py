import json
import re
import asyncio
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

load_dotenv()

# 1. 커리큘럼 설계를 위한 시스템 프롬프트
CURRICULUM_SYSTEM_PROMPT = """당신은 IT 교육 기관의 수석 교육과정 설계자(Instructional Designer)인 CourseAgent::Curriculum입니다.
제시된 교육과정명과 과정 설명을 바탕으로, 비전공자도 쉽게 배울 수 있도록 구조화된 8주차 분량의 주간 실무 커리큘럼을 설계해야 합니다.

[답변 포맷]
반드시 아래 JSON 포맷만을 반환해 주세요. 다른 인사말이나 마크다운 백틱(```json) 기호 등 부가 텍스트는 일절 출력하지 마세요.

[
  {{
    "week": 1,
    "topic": "1주차 핵심 대주제명",
    "details": "1주차에 배울 구체적인 실무 세부 기술 키워드 및 학습 내용 요약 (쉼표로 구분)"
  }},
  ...
  {{
    "week": 8,
    "topic": "8주차 핵심 대주제명",
    "details": "8주차에 배울 구체적인 실무 세부 기술 키워드 및 학습 내용 요약 (쉼표로 구분)"
  }}
]
"""

# 2. 강의안 상세 저작을 위한 시스템 프롬프트
LECTURE_PLAN_SYSTEM_PROMPT = """당신은 IT/SW 전문 강사인 CourseAgent::Lecture입니다.
교육과정명, 주차, 대주제, 세부 학습 내용을 참고하여, 강사가 실제 수업 시간에 슬라이드로 사용하거나 가이드로 삼을 수 있는 매우 친절하고 분량이 상세한 강의 계획안을 작성해 주세요.

[강의안 구성 가이드라인]
마크다운(Markdown) 문법을 사용해 가독성 있게 작성하세요:
1. # [주차] 대주제 강의안 (대제목)
2. ## 1. 핵심 학습 목표 (최소 2개 이상)
3. ## 2. 상세 이론 설명 (핵심 원리와 키워드를 깊이 있게 서술)
4. ## 3. 실무 예제 코드 & 실습 가이드 (실무에서 즉시 활용 가능한 에러 없는 완성형 코드 블록 제공)
5. ## 4. 강사 전용 교수법 가이드 (수업을 매끄럽게 운영하기 위한 팁, 학생들의 잦은 에러 예방 방안)

경어체(존댓말)로 정중하고 깊이 있게 서술해 주세요.
"""

# 3. 시험문제 자동 출제를 위한 시스템 프롬프트 (정답 해설 explanation 필드 의무화)
EXAM_SYSTEM_PROMPT = """당신은 평가 설계 전문가인 CourseAgent::Exam입니다.
교육과정명, 과목명, 핵심 주제 키워드를 바탕으로 해당 과목을 완수한 학생들이 응시할 총 5문항의 종합 평가 시험 문제지를 출제해 주세요.

[출제 기준]
- 1번, 2번, 3번 문제: 객관식(4지선다형) 문항. ("type": "choice")
- 4번 문제: 주관식 서술형 문항. 개념이나 원리 기술. ("type": "descriptive", 채점용 "keywords" 리스트와 모범 답안 가이드 "answer_guide" 포함)
- 5번 문제: 코딩/실습 구현 완성 문항. 특정 함수나 Hook 구현. ("type": "coding", 채점용 "keywords" 리스트와 모범 답안 가이드 "answer_guide" 포함)
- **중요**: 모든 문항(1~5번)은 반드시 정답의 원리와 배경을 담은 `"explanation"` (상세 해설) 필드를 가져야 합니다.

[답변 포맷]
반드시 아래 JSON 구조의 데이터만 출력해야 하며, 코드 블록 기호(```json)나 추가 해설은 전부 생략해 주세요.

[
  {{
    "type": "choice",
    "number": 1,
    "question": "1번 객관식 문제 질문",
    "options": ["1) 보기1", "2) 보기2", "3) 보기3", "4) 보기4"],
    "answer": "정답 번호 문자열 ('1', '2', '3', '4' 중 하나)",
    "explanation": "해당 문항 정답에 대한 구체적 해설"
  }},
  {{
    "type": "choice",
    "number": 2,
    "question": "2번 객관식 문제 질문",
    "options": ["1) 보기1", "2) 보기2", "3) 보기3", "4) 보기4"],
    "answer": "정답 번호 문자열 ('1', '2', '3', '4' 중 하나)",
    "explanation": "해당 문항 정답에 대한 구체적 해설"
  }},
  {{
    "type": "choice",
    "number": 3,
    "question": "3번 객관식 문제 질문",
    "options": ["1) 보기1", "2) 보기2", "3) 보기3", "4) 보기4"],
    "answer": "정답 번호 문자열 ('1', '2', '3', '4' 중 하나)",
    "explanation": "해당 문항 정답에 대한 구체적 해설"
  }},
  {{
    "type": "descriptive",
    "number": 4,
    "question": "4번 주관식 서술형 질문",
    "keywords": ["채점 시 답변에 필수 포함되어야 할 핵심 키워드 단어 최소 3개 이상"],
    "answer_guide": "채점 기준이 되는 구체적인 모범 답안 가이드",
    "explanation": "모범 답안 논리 및 핵심 이론 배경 해설"
  }},
  {{
    "type": "coding",
    "number": 5,
    "question": "5번 코딩/실습 구현 완성 질문",
    "keywords": ["코드 채점 시 들어가야 할 핵심 라이브러리/메서드/구문 키워드 3개 이상"],
    "answer_guide": "모범 완성 코드 및 설명",
    "explanation": "코딩 구현 시 지켜야 할 이론적 배경 및 해법 코드 상세 분석 해설"
  }}
]
"""

# 4. 단일 문항 대체를 위한 시스템 프롬프트
SINGLE_QUESTION_SYSTEM_PROMPT = """당신은 평가 설계 전문가인 CourseAgent::SingleQuestion입니다.
교육과정명, 과목명, 핵심 주제 정보를 바탕으로, 지정된 문제 번호와 유형에 맞는 단 하나의 새로운 시험 문항을 출제해 주세요.

[요구 문제 정보]
- 문제 번호: {number}
- 문제 유형: {type} (choice: 객관식, descriptive: 주관식 서술형, coding: 코딩실습형)

[출제 기준]
- 객관식("type": "choice"): 4지선다형 문항으로, 질문, 보기 4개, 정답 번호("answer"), 그리고 상세 정답 해설("explanation")을 작성하세요.
- 주관식 서술형("type": "descriptive"): 질문, 채점 키워드("keywords"), 모범 답안 가이드("answer_guide"), 그리고 정답 해설("explanation")을 작성하세요.
- 코딩실습형("type": "coding"): 질문, 채점 키워드("keywords"), 모범 답안 가이드("answer_guide"), 그리고 정답 해설("explanation")을 작성하세요.

[답변 포맷]
반드시 아래 JSON 구조의 데이터만 출력해야 하며, 코드 블록 기호(```json)나 추가 해설은 전부 생략해 주세요.

{{
  "type": "{type}",
  "number": {number},
  "question": "출제 문제 질문 내용",
  "options": ["1) 보기1", "2) 보기2", "3) 보기3", "4) 보기4"], // choice형일 때만 채우고, 다른 유형은 빈 배열 []
  "answer": "객관식일 때 정답 번호 문자열 ('1', '2', '3', '4' 중 하나). 주관식/코딩은 빈 문자열 ''",
  "keywords": ["채점 시 필수 포함 핵심 키워드 목록"], // 주관식/코딩일 때만 채우고, 객관식은 빈 배열 []
  "answer_guide": "모범 답안 가이드 내용", // 주관식/코딩일 때만 채우고, 객관식은 빈 문자열 ''
  "explanation": "해당 문항의 상세한 풀이 및 해설"
}}
"""

async def generate_curriculum_async(course_name: str, course_desc: str) -> list:
    """
    과정명과 개요를 바탕으로 8주차 커리큘럼 데이터(JSON 리스트)를 생성합니다.
    """
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.2)
    prompt = ChatPromptTemplate.from_messages([
        ("system", CURRICULUM_SYSTEM_PROMPT),
        ("human", "과정명: {name}\n과정 설명: {desc}")
    ])
    
    response = await llm.ainvoke(prompt.format(name=course_name, desc=course_desc))
    res_text = response.content.strip()
    res_text = re.sub(r"^```json\s*", "", res_text)
    res_text = re.sub(r"\s*```$", "", res_text)
    
    try:
        curriculum_list = json.loads(res_text)
        return curriculum_list
    except Exception as e:
        print(f"Curriculum JSON Error: {e}\nRaw Text: {res_text}")
        return [{"week": i, "topic": f"{course_name} 기초 {i}단계", "details": "세부 키워드 준비 중"} for i in range(1, 9)]

async def generate_lecture_plan_async(course_name: str, week: int, topic: str, details: str) -> str:
    """
    주차별 주제를 바탕으로 상세 마크다운 강의안을 생성합니다.
    """
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3)
    prompt = ChatPromptTemplate.from_messages([
        ("system", LECTURE_PLAN_SYSTEM_PROMPT),
        ("human", "교육과정명: {course_name}\n주차: {week}주차\n대주제: {topic}\n세부 내용: {details}")
    ])
    
    response = await llm.ainvoke(prompt.format(course_name=course_name, week=week, topic=topic, details=details))
    return response.content

async def generate_exam_async(course_name: str, subject_name: str, key_topics: str) -> list:
    """
    과목명과 주제 정보를 바탕으로 5문항의 시험 문제를 생성합니다.
    """
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.4)
    prompt = ChatPromptTemplate.from_messages([
        ("system", EXAM_SYSTEM_PROMPT),
        ("human", "교육과정명: {course_name}\n평가 과목명: {subject_name}\n핵심 주제 정보: {topics}")
    ])
    
    response = await llm.ainvoke(prompt.format(course_name=course_name, subject_name=subject_name, topics=key_topics))
    res_text = response.content.strip()
    res_text = re.sub(r"^```json\s*", "", res_text)
    res_text = re.sub(r"\s*```$", "", res_text)
    
    try:
        exam_questions = json.loads(res_text)
        return exam_questions
    except Exception as e:
        print(f"Exam JSON Error: {e}\nRaw Text: {res_text}")
        return [
            {"type": "choice", "number": 1, "question": f"{subject_name} 관련 기본 문제", "options": ["1) 보기A", "2) 보기B", "3) 보기C", "4) 보기D"], "answer": "1", "explanation": "폴백 설명"},
            {"type": "choice", "number": 2, "question": f"{subject_name} 관련 기본 문제 2", "options": ["1) 보기A", "2) 보기B", "3) 보기C", "4) 보기D"], "answer": "1", "explanation": "폴백 설명"},
            {"type": "choice", "number": 3, "question": f"{subject_name} 관련 기본 문제 3", "options": ["1) 보기A", "2) 보기B", "3) 보기C", "4) 보기D"], "answer": "1", "explanation": "폴백 설명"},
            {"type": "descriptive", "number": 4, "question": f"{subject_name}의 동작 원리를 서술하시오.", "keywords": ["동작", "원리"], "answer_guide": "모범 답안", "explanation": "폴백 설명"},
            {"type": "coding", "number": 5, "question": f"{subject_name} 관련 코드를 작성하시오.", "keywords": ["code"], "answer_guide": "code", "explanation": "폴백 설명"}
        ]

async def generate_single_question_async(course_name: str, subject_name: str, question_number: int, question_type: str, key_topics: str) -> dict:
    """
    단일 특정 문항번호 및 유형에 부합하는 새로운 시험 문제를 AI로 생성하여 반환합니다.
    """
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.6) # 다양성을 위해 온도를 살짝 높임
    prompt = ChatPromptTemplate.from_messages([
        ("system", SINGLE_QUESTION_SYSTEM_PROMPT),
        ("human", "교육과정명: {course_name}\n평가 과목명: {subject_name}\n핵심 주제 정보: {topics}")
    ])
    
    response = await llm.ainvoke(prompt.format(
        number=question_number,
        type=question_type,
        course_name=course_name,
        subject_name=subject_name,
        topics=key_topics
    ))
    res_text = response.content.strip()
    res_text = re.sub(r"^```json\s*", "", res_text)
    res_text = re.sub(r"\s*```$", "", res_text)
    
    try:
        single_q = json.loads(res_text)
        return single_q
    except Exception as e:
        print(f"Single Question JSON Error: {e}\nRaw Text: {res_text}")
        # 폴백
        if question_type == "choice":
            return {
                "type": "choice",
                "number": question_number,
                "question": f"{subject_name} 관련 신규 객관식 문제",
                "options": ["1) 보기1", "2) 보기2", "3) 보기3", "4) 보기4"],
                "answer": "1",
                "explanation": "재생성 폴백 설명"
            }
        else:
            return {
                "type": question_type,
                "number": question_number,
                "question": f"{subject_name} 관련 신규 서술/코딩 문제",
                "keywords": ["재생성"],
                "answer_guide": "가이드",
                "explanation": "재생성 폴백 설명"
            }

async def handle_course_query(query_str: str) -> str:
    """
    자연어 요청 디스패처
    """
    from database import insert_course, insert_curriculum, insert_lecture_plan, insert_exam
    
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    
    intent_prompt = ChatPromptTemplate.from_messages([
        ("system", "사용자의 교육 설계 및 자료 생성 요청을 분석하여 다음 3가지 의도 중 하나로 분류하고 JSON 포맷으로 출력하세요.\n"
                   "1. `curriculum`: 새로운 교육과정 개설 및 8주차 커리큘럼 설계 (예: 'React 과정 커리큘럼 짜줘')\n"
                   "2. `lecture_plan`: 특정 주제나 주차에 대한 강의계획서/강의안 작성 (예: 'CSS 레이아웃 강의안 작성해줘')\n"
                   "3. `exam`: 과목별 시험지 자동 출제 (예: 'FastAPI 시험 출제해줘')\n\n"
                   "출력 포맷: 반드시 아래 JSON 구조만 출력해야 하며 다른 텍스트나 백틱 기호는 생략하세요.\n"
                   "{{{\"intent\": \"curriculum\" | \"lecture_plan\" | \"exam\", \"course_name\": \"과정명\", \"subject_name\": \"과목/주제명\", \"description_or_details\": \"세부 설명 또는 출제 지시 키워드\"}}}"),
        ("human", "사용자 요청: {query}")
    ])
    
    response = await llm.ainvoke(intent_prompt.format(query=query_str))
    res_text = response.content.strip()
    res_text = re.sub(r"^```json\s*", "", res_text)
    res_text = re.sub(r"\s*```$", "", res_text)
    
    try:
        data = json.loads(res_text)
        intent = data.get("intent", "curriculum")
        course_name = data.get("course_name", "신규 과정")
        subject_name = data.get("subject_name", "기초 과목")
        details = data.get("description_or_details", "")
        
        if intent == "curriculum":
            curr_list = await generate_curriculum_async(course_name, details)
            c_id = insert_course(course_name, details)
            for item in curr_list:
                insert_curriculum(c_id, item["week"], item["topic"], item["details"])
            
            report = f"### 🆕 교육과정 '{course_name}' 등록 및 8주 커리큘럼 설계 완료\n\n"
            report += f"* **교육과정 설명**: {details}\n\n"
            for item in curr_list:
                report += f"- **{item['week']}주차**: {item['topic']}\n  * *내용*: {item['details']}\n"
            report += f"\n[출처: course_agent | SQLite DB 등록 완료]"
            return report
            
        elif intent == "lecture_plan":
            plan_content = await generate_lecture_plan_async(course_name, 1, subject_name, details)
            insert_lecture_plan(1, subject_name, plan_content)
            return f"{plan_content}\n\n[출처: course_agent | SQLite DB 등록 완료]"
            
        elif intent == "exam":
            # 자동 생성 후 바로 DB 저장 (미리보기를 거치지 않는 다이렉트 출제 챗봇 모드)
            questions_list = await generate_exam_async(course_name, subject_name, details)
            insert_exam(1, subject_name, questions_list)
            
            report = f"### 📝 과목 '{subject_name}' 신규 평가 시험 출제 완료 (5문항)\n\n"
            for q in questions_list:
                q_type_ko = "객관식" if q["type"] == "choice" else "주관식 서술형" if q["type"] == "descriptive" else "코딩실습형"
                report += f"**{q['number']}. {q['question']}** ({q_type_ko})\n"
                if q["type"] == "choice":
                    for opt in q["options"]:
                        report += f"  - {opt}\n"
            report += f"\n[출처: course_agent | SQLite DB 등록 완료]"
            return report
            
    except Exception as e:
        print(f"Error handling course query: {e}\nRaw JSON: {res_text}")
        return f"교육과정 및 자료를 저작하는 도중 오류가 발생했습니다: {e}"

if __name__ == "__main__":
    # 단위 테스트
    async def test():
        print("Testing single question generation...")
        res = await generate_single_question_async("React Core", "Hooks 평가", 4, "descriptive", "useEffect, cleanup")
        print(json.dumps(res, indent=2, ensure_ascii=False))
        
    asyncio.run(test())
