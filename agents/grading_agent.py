import json
import re
import asyncio
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

load_dotenv()

# 주관식/코딩 문제 채점을 위한 시스템 프롬프트
GRADING_SYSTEM_PROMPT = """당신은 수강생들의 주관식 서술형 및 코딩 시험 답안을 채점하는 전문 채점 위원인 GradingAgent입니다.
출제된 문제 정보(질문, 채점 키워드, 모범 답안 가이드)와 학생이 제출한 답안이 제공됩니다.
각 문제당 20점 만점 기준으로 학생의 답안을 공정하게 평가하여 점수와 개별 피드백을 도출해 주세요.

[채점 기준 지침]
- **키워드 일치성**: 제시된 채점 키워드들이 의미상 또는 명시적으로 충분히 들어가 있는지 확인하세요.
- **개념적 이해**: 단순히 키워드 나열이 아니라 질문의 의도에 맞게 문장을 구성하고 로직을 설계했는지 파악하세요.
- **부분 점수 부여**:
  - 완벽한 정답 (키워드 모두 충족 및 개념 완벽): 20점
  - 핵심 키워드가 일부 빠졌거나 설명이 조금 부족한 경우: 10~15점
  - 아예 엉뚱한 대답이거나 미흡한 단답: 0~5점

[답변 포맷]
반드시 아래 XML 구조로만 답변을 출력해 주세요. 다른 인사말이나 설명은 작성하지 마세요.

<grading>
<question4>
<score>[4번 문항 점수 - 정수만 기재, 예: 15]</score>
<feedback>[4번 문항에 대한 구체적인 채점 소평 및 오답 시 피드백 요약]</feedback>
</question4>
<question5>
<score>[5번 문항 점수 - 정수만 기재, 예: 20]</score>
<feedback>[5번 문항 코딩 답안에 대한 구체적인 채점 소평 및 코드 개선점 피드백]</feedback>
</question5>
<overall_comment>[학생 전체 답안을 아우르는 따뜻하고 유익한 격려 섞인 종합 총평]</overall_comment>
</grading>
"""

async def grade_exam_submission_async(questions: list, student_answers: list) -> tuple:
    """
    학생의 제출 답안을 채점하여 (최종 점수: int, 마크다운 피드백 리포트: str) 튜플을 반환합니다.
    """
    # 점수 계산 및 피드백 빌더
    total_score = 0
    q_reports = {}
    
    # 1. 1~3번 객관식 채점 (프로그래밍 방식)
    for q in questions[:3]:
        q_num = q["number"]
        correct_ans = q["answer"].strip()
        
        # 학생의 제출 답 찾기
        student_ans_dict = next((a for a in student_answers if a["number"] == q_num), None)
        student_ans = student_ans_dict["answer"].strip() if student_ans_dict else ""
        
        if student_ans == correct_ans:
            total_score += 20
            q_reports[q_num] = {
                "status": "정답 (+20점)",
                "correct": correct_ans,
                "student": student_ans,
                "score": 20,
                "feedback": "정답입니다."
            }
        else:
            q_reports[q_num] = {
                "status": "오답 (0점)",
                "correct": correct_ans,
                "student": student_ans,
                "score": 0,
                "feedback": f"틀렸습니다. (정답: {correct_ans}번 / 제출: {student_ans}번)"
            }

    # 2. 4~5번 주관식 및 코딩 채점 (LLM 방식)
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.1)
    prompt = ChatPromptTemplate.from_messages([
        ("system", GRADING_SYSTEM_PROMPT),
        ("human", "문제4 정보: {q4_info}\n학생4 답안: {q4_ans}\n\n문제5 정보: {q5_info}\n학생5 답안: {q5_ans}")
    ])
    
    q4 = questions[3]
    q5 = questions[4]
    
    q4_info = f"질문: {q4['question']}\n채점키워드: {q4.get('keywords', [])}\n모범답안가이드: {q4.get('answer_guide', '')}"
    q5_info = f"질문: {q5['question']}\n채점키워드: {q5.get('keywords', [])}\n모범답안가이드: {q5.get('answer_guide', '')}"
    
    ans4_dict = next((a for a in student_answers if a["number"] == 4), None)
    ans5_dict = next((a for a in student_answers if a["number"] == 5), None)
    
    q4_ans = ans4_dict["answer"] if ans4_dict else "답변 미제출"
    q5_ans = ans5_dict["answer"] if ans5_dict else "답변 미제출"
    
    response = await llm.ainvoke(prompt.format(
        q4_info=q4_info, q4_ans=q4_ans,
        q5_info=q5_info, q5_ans=q5_ans
    ))
    res_text = response.content.strip()

    # XML 파싱
    q4_score = 0
    q4_feedback = "채점 중 오류가 발생했습니다."
    q5_score = 0
    q5_feedback = "채점 중 오류가 발생했습니다."
    overall_comment = "채점을 성공적으로 마무리하지 못했습니다."

    try:
        q4_score_match = re.search(r"<question4>\s*<score>(.*?)</score>", res_text, re.DOTALL)
        q4_feedback_match = re.search(r"<question4>.*?<feedback>(.*?)</feedback>", res_text, re.DOTALL)
        q5_score_match = re.search(r"<question5>\s*<score>(.*?)</score>", res_text, re.DOTALL)
        q5_feedback_match = re.search(r"<question5>.*?<feedback>(.*?)</feedback>", res_text, re.DOTALL)
        overall_match = re.search(r"<overall_comment>(.*?)</overall_comment>", res_text, re.DOTALL)

        if q4_score_match:
            q4_score = int(q4_score_match.group(1).strip())
        if q4_feedback_match:
            q4_feedback = q4_feedback_match.group(1).strip()
            
        if q5_score_match:
            q5_score = int(q5_score_match.group(1).strip())
        if q5_feedback_match:
            q5_feedback = q5_feedback_match.group(1).strip()
            
        if overall_match:
            overall_comment = overall_match.group(1).strip()
            
        total_score += (q4_score + q5_score)
    except Exception as e:
        print(f"Error parsing grading response: {e}\nRaw Response: {res_text}")
        overall_comment = "채점 데이터를 파싱하는 도중 오류가 발생했습니다."

    # 3. 채점 리포트 마크다운 완성
    report = f"""## 📝 AI 시험 채점 결과 리포트

- **최종 획득 점수**: **{total_score}점** / 100점 만점

### 🔍 문항별 채점 상세

1. **1번 문항 (객관식)**: **{q_reports[1]['status']}**
   - 제출 답안: {q_reports[1]['student']}번 | 정답: {q_reports[1]['correct']}번
   
2. **2번 문항 (객관식)**: **{q_reports[2]['status']}**
   - 제출 답안: {q_reports[2]['student']}번 | 정답: {q_reports[2]['correct']}번
   
3. **3번 문항 (객관식)**: **{q_reports[3]['status']}**
   - 제출 답안: {q_reports[3]['student']}번 | 정답: {q_reports[3]['correct']}번

4. **4번 문항 (주관식 서술형)**: **{q4_score}점** / 20점
   - *피드백*: {q4_feedback}

5. **5번 문항 (코딩 실습형)**: **{q5_score}점** / 20점
   - *피드백*: {q5_feedback}

### 💡 평가 총평
{overall_comment}

[출처: grading_agent]
"""
    
    # 구조화된 세부 성적 데이터를 JSON으로 패키징
    result_data = {
        "report_md": report,
        "overall_comment": overall_comment,
        "q_reports": {
            "1": {
                "score": q_reports[1]["score"],
                "feedback": q_reports[1]["feedback"],
                "student": q_reports[1]["student"],
                "correct": q_reports[1]["correct"],
                "status": q_reports[1]["status"]
            },
            "2": {
                "score": q_reports[2]["score"],
                "feedback": q_reports[2]["feedback"],
                "student": q_reports[2]["student"],
                "correct": q_reports[2]["correct"],
                "status": q_reports[2]["status"]
            },
            "3": {
                "score": q_reports[3]["score"],
                "feedback": q_reports[3]["feedback"],
                "student": q_reports[3]["student"],
                "correct": q_reports[3]["correct"],
                "status": q_reports[3]["status"]
            },
            "4": {
                "score": q4_score,
                "feedback": q4_feedback,
                "student": q4_ans,
                "status": f"{q4_score}점"
            },
            "5": {
                "score": q5_score,
                "feedback": q5_feedback,
                "student": q5_ans,
                "status": f"{q5_score}점"
            }
        }
    }
    
    return total_score, json.dumps(result_data, ensure_ascii=False)


if __name__ == "__main__":
    # 단위 테스트
    async def test():
        sample_questions = [
            {"number": 1, "question": "Q1", "options": [], "answer": "2"},
            {"number": 2, "question": "Q2", "options": [], "answer": "2"},
            {"number": 3, "question": "Q3", "options": [], "answer": "1"},
            {"number": 4, "question": "useEffect의 클린업 기능과 타이머 해제 상황을 적으시오.", "keywords": ["타이머", "해제", "정리"], "answer_guide": "메모리 누수 방지용"},
            {"number": 5, "question": "fetch API로 데이터 세팅 함수 작성.", "keywords": ["fetch", "setData"], "answer_guide": "fetch('url')"}
        ]
        sample_answers = [
            {"number": 1, "answer": "2"},
            {"number": 2, "answer": "1"},
            {"number": 3, "answer": "1"},
            {"number": 4, "answer": "화면에서 컴포넌트가 정리될 때 타이머 해제 처리를 하지 않으면 메모리가 누수되므로 클린업을 씁니다."},
            {"number": 5, "answer": "const f = () => { fetch('url').then(res => res.json()).then(data => setData(data)) }"}
        ]
        
        score, rep = await grade_exam_submission_async(sample_questions, sample_answers)
        print(f"Total Score: {score}")
        print(rep)
        
    asyncio.run(test())
