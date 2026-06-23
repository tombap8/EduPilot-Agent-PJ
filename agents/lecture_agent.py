import os
import asyncio
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

load_dotenv()

# 경로 설정
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
CHROMA_DIR = os.path.join(PROJECT_ROOT, "chroma_db")
DOCS_DIR = os.path.join(PROJECT_ROOT, "docs")

def find_all_pdfs(directory):
    """지정된 디렉토리와 하위 디렉토리에서 모든 PDF 파일을 찾습니다."""
    pdf_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.lower().endswith(".pdf"):
                pdf_files.append(os.path.join(root, file))
    return pdf_files

def ingest_documents():
    """docs 폴더의 모든 PDF 파일을 Chroma DB에 임베딩하여 적재합니다."""
    pdf_paths = find_all_pdfs(DOCS_DIR)
    documents = []
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)

    for path in pdf_paths:
        try:
            # 기획서 proposal 자체는 인제스션에서 제외 (강의 자료가 아님)
            if os.path.basename(path) == "edupilot_project_proposal.pdf":
                continue
            
            loader = PyPDFLoader(path)
            file_docs = loader.load()
            
            # 메타데이터에 파일명 삽입
            for doc in file_docs:
                doc.metadata["source_file"] = os.path.basename(path)
                
            documents.extend(file_docs)
            print(f"Loaded: {os.path.basename(path)} ({len(file_docs)} pages)")
        except Exception as e:
            print(f"Error loading {path}: {e}")

    if not documents:
        print("No documents found to ingest.")
        return 0

    chunks = text_splitter.split_documents(documents)
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    
    # Chroma 인스턴스 생성 및 로컬 저장
    db = Chroma.from_documents(chunks, embeddings, persist_directory=CHROMA_DIR)
    db.persist()
    print(f"Successfully ingested {len(chunks)} chunks into Chroma DB.")
    return len(chunks)

async def query_lecture_async(query_str: str) -> str:
    """
    Chroma VectorDB에서 질의어와 연관된 문서 조각을 찾아
    gpt-4o-mini 모델로 답변을 생성하고 출처를 함께 표기합니다. (비동기 지원)
    """
    # 임베딩 생성 및 Chroma 로드
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    
    # 만약 chroma_db 폴더가 없거나 비어 있다면, 먼저 자동 인제스션을 시도합니다.
    if not os.path.exists(CHROMA_DIR) or not os.listdir(CHROMA_DIR):
        print("Chroma DB not found. Running automatic ingestion...")
        # 블로킹 작업이므로 스레드 풀에서 실행
        await asyncio.to_thread(ingest_documents)

    db = Chroma(persist_directory=CHROMA_DIR, embedding_function=embeddings)
    
    # 유사도 기반 검색 (k=4)
    retriever = db.as_retriever(search_kwargs={"k": 4})
    # 동기 호출 함수이므로 to_thread를 사용하여 비동기 처리
    docs = await asyncio.to_thread(retriever.invoke, query_str)
    
    if not docs:
        return "강의 자료에서 관련 내용을 찾을 수 없습니다. 새로운 PDF 문서를 업로드해 주시기 바랍니다."

    # 컨텍스트 빌드 및 출처 수집
    context = ""
    for doc in docs:
        source_name = doc.metadata.get("source_file", "알 수 없음")
        page_num = doc.metadata.get("page", 0) + 1
        context += f"\n--- [출처: {source_name} ({page_num}페이지)] ---\n{doc.page_content}\n"

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    prompt = ChatPromptTemplate.from_messages([
        ("system", "당신은 강의 자료를 기반으로 질문에 대답하는 Lecture Agent입니다. "
                   "제시된 컨텍스트(강의 교재 스니펫) 내용을 근거로 질문에 명확하고 정확하게 답변해 주세요. "
                   "컨텍스트에 정보가 없다면 억지로 꾸며내지 말고 솔직하게 모른다고 대답하세요. "
                   "답변의 마지막 줄에는 참고한 파일명과 페이지들을 종합하여 '[출처: 파일명 (페이지p)]' 형태로 명시해 주세요."),
        ("human", "질문: {query}\n\n컨텍스트 정보:\n{context}")
    ])

    chain = prompt | llm
    response = await llm.ainvoke(prompt.format(query=query_str, context=context))
    return response.content

if __name__ == "__main__":
    # 단위 테스트 코드
    print("Ingesting documents...")
    ingest_documents()
    print("Querying React useEffect test...")
    res = asyncio.run(query_lecture_async("React useEffect 사용법에 대해 설명해줘"))
    print("\n[Result]:")
    print(res)
