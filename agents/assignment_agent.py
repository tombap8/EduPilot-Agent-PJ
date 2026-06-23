import asyncio
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

load_dotenv()

# 코드 리뷰 피드백 작성을 위한 시스템 프롬프트
REVIEW_SYSTEM_PROMPT = """당신은 현업 리드 개발자이자 코딩 멘토인 Assignment Review Agent입니다.
학생이 제출한 소스코드를 분석하여 개발 성장에 도움을 주는 종합 피드백 리포트를 작성해 주세요.

[리뷰 범위 및 구성]
1. **코드 개요**: 코드가 무엇을 수행하는지 핵심 로직과 기능 설명.
2. **구문 오류 및 안티패턴**: 구문 오류(Syntax Error)나 모범 사례(Best Practices)에 어긋나는 부분, 안티패턴 지적.
3. **성능 및 가독성 개선 제안**: 성능을 향상시키거나 코드를 더 읽기 쉽게 만들기 위한 리팩토링 방안 및 개선된 예시 코드 제공.
4. **구현 난이도 및 평가**: 상/중/하 난이도 및 학생의 이해 수준에 대한 종합적인 격려 섞인 코멘트.

[어조 및 포맷]
- 친절하고 격려하는 말투(해요체, 존댓말)를 사용하세요.
- 마크다운 서식을 사용하여 각 파트를 명확히 구분해 가독성을 최대화하세요.
- 코드 블록을 제공할 때는 해당 언어(예: python, javascript)를 명시해 주세요.
- 답변 마지막 줄에 '[출처: code_review_model]' 문구를 기재해 주세요.
"""

async def review_assignment_async(code_content: str, programming_language: str = "auto") -> str:
    """
    제출된 소스코드를 분석하여 마크다운 포맷의 상세 코드 리뷰 리포트를 생성합니다.
    """
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.2) # 정교하고 정확한 코드 분석을 위해 낮은 온도로 설정

    prompt = ChatPromptTemplate.from_messages([
        ("system", REVIEW_SYSTEM_PROMPT),
        ("human", "제출된 소스코드 (언어: {language}):\n\n```\n{code}\n```")
    ])

    response = await llm.ainvoke(prompt.format(language=programming_language, code=code_content))
    return response.content

if __name__ == "__main__":
    # 단위 테스트 코드
    async def test():
        sample_code = """
        function TodoList() {
          const [todos, setTodos] = React.useState([]);
          
          const addTodo = (text) => {
            // direct state mutation - anti pattern
            todos.push({ id: Date.now(), text: text });
            setTodos(todos);
          };
          
          return (
            <div>
              <button onClick={() => addTodo("New Task")}>Add</button>
            </div>
          );
        }
        """
        res = await review_assignment_async(sample_code, "javascript/react")
        print("\n[Code Review Report]:")
        print(res)
        
    asyncio.run(test())
