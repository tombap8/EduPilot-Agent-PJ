import os
import sqlite3
import re
import asyncio
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from database import DB_PATH, insert_announcement

load_dotenv()

# 공지사항 작성을 위한 시스템 프롬프트
NOTICE_SYSTEM_PROMPT = """당신은 교육 기관에서 수강생 및 학부모를 대상으로 정중하고 명확한 안내 공지사항을 작성하는 Notice Agent입니다.
제시된 정보(컨텍스트 및 지시사항)를 바탕으로 완성도 높고 격식 있는 공지문을 마크다운 형식으로 자동 작성해 주세요.

[공지문 형식 가이드라인]
1. 정중한 경어체(존댓말) 사용.
2. 중요 정보(일시, 대상, 마감 기한, 평가 범위 등)는 이모티콘과 불릿 포인트를 사용하여 가독성 있게 구조화.
3. 실무에서 즉시 복사하여 알림톡(카카오톡)이나 LMS 공지 게시판에 기재할 수 있도록 실용적이고 완성된 텍스트 제공.
4. 제목(Title)과 본문(Content)을 명확하게 구분하여 작성.

[답변 포맷]
반드시 아래의 XML 마크업 형식을 철저히 지켜 출력해 주세요. 다른 앞뒤 인사말이나 추가 설명은 일절 포함하지 마세요.
<announcement>
<title>[공지사항 제목 작성]</title>
<content>[공지사항 본문 내용 작성]</content>
</announcement>
"""

async def generate_notice_async(instruction: str, context_str: str = "") -> dict:
    """
    강사의 요청(instruction)과 보조 컨텍스트(context_str)를 활용하여 공지사항을 생성하고,
    SQLite DB에 저장한 후 생성된 공지사항 딕셔너리(title, content)를 반환합니다.
    """
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7) # 창의적인 문장 작성을 위해 온도를 살짝 높임

    prompt = ChatPromptTemplate.from_messages([
        ("system", NOTICE_SYSTEM_PROMPT),
        ("human", "작성 요청: {instruction}\n\n참고 컨텍스트 정보:\n{context}")
    ])

    response = await llm.ainvoke(prompt.format(instruction=instruction, context=context_str))
    response_text = response.content.strip()

    # XML 파싱
    title = "공지사항"
    content = ""
    
    title_match = re.search(r"<title>(.*?)</title>", response_text, re.DOTALL)
    content_match = re.search(r"<content>(.*?)</content>", response_text, re.DOTALL)

    if title_match:
        title = title_match.group(1).strip()
    if content_match:
        content = content_match.group(1).strip()
    else:
        # 파싱 실패 시 예외 처리 및 폴백
        content = response_text

    # SQLite DB에 공지사항 적재
    if os.path.exists(DB_PATH):
        try:
            # 블로킹 작업이므로 스레드 풀에서 DB 인서트
            await asyncio.to_thread(insert_announcement, title, content)
            print(f"[Notice Saved to DB]: {title}")
        except Exception as e:
            print(f"Error saving notice to DB: {e}")
    else:
        print("Database not found. Notice generated but not saved to SQLite.")

    return {
        "title": title,
        "content": content
    }

if __name__ == "__main__":
    # 단위 테스트 코드
    async def test():
        res = await generate_notice_async(
            instruction="다음 주 React 과제 마감일(6월 28일 23:59)과 평가 일정(7주차 실기평가)을 안내하는 공지문 작성해줘",
            context_str="2차 실기 평가 (대기), React 쇼핑몰 카트 구현"
        )
        print("\n[Generated Notice]:")
        print(f"TITLE: {res['title']}")
        print(f"CONTENT:\n{res['content']}")
        
    asyncio.run(test())
