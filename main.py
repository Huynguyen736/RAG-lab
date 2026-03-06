__import__('pysqlite3')
import sys
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, END
from typing import TypedDict, List, Dict
from dotenv import load_dotenv
from os import getenv, path, makedirs, chmod
import json
import time
import shutil
from fastapi import FastAPI
from mangum import Mangum

load_dotenv()
GEMINI_API_KEY = getenv("GEMINI_API_KEY")
ORIGINAL_DB_DIR = "/var/task/db" 
DB_DIR = "/tmp/db"

if not path.exists(DB_DIR):
    if path.exists(ORIGINAL_DB_DIR):
        shutil.copytree(ORIGINAL_DB_DIR, DB_DIR)
        chmod(DB_DIR, 0o777)
    else:
        makedirs(DB_DIR, exist_ok=True)

class GraphState(TypedDict):
    query: str
    chunks: List[Dict]
    generation: str
    retries: int

# splitter
splitter = RecursiveCharacterTextSplitter(
    chunk_size = 500,
    chunk_overlap = 100
)

# embedding
embedding = GoogleGenerativeAIEmbeddings(
    model="gemini-embedding-001",
    api_key=GEMINI_API_KEY
)

# vector store (ChromaDB)
vector_store = Chroma(
    collection_name="policy_data",
    embedding_function=embedding,
    persist_directory=DB_DIR)

# llm
llm = ChatGoogleGenerativeAI(
    model = "gemini-3-flash-preview",
    api_key = GEMINI_API_KEY
)

def retrieve_node(state: GraphState):
    """Returns relevant policies"""
    print("\n--- NODE 1: RETRIEVER ---")
    query = state["query"]
    start = time.time()
    results = vector_store.similarity_search_with_relevance_scores(query, k = 3)

    retrieved_context = []
    for doc, score in results:
        context_item = {
            "content": doc.page_content,
            "page": doc.metadata.get("page", "N/A"),
            "score": round(score, 4)
        }
        retrieved_context.append(context_item)
    
    print("Retrieve time:", time.time() - start)

    return {"chunks": retrieved_context}

def generate_node(state: GraphState):
    """Create JSON response from chunks + query"""
    print("--- NODE 2: GENERATOR ---")
    start = time.time()
    query = state["query"]
    chunks = state["chunks"]
    error = state.get("error")
    context_str = "\n\n-----\n\n".join([f"Relevance chunk {i}. (Page {c['page']} ; score: {c['score']}):\n{c['content']}" for i, c in enumerate(chunks, 1)])

    system_prompt = """You are a strict corporate policy auditor. 
    Answer the user's query using ONLY the provided context.
    You MUST respond with a valid, raw JSON object exactly matching this format:
    {{"answer": "Your concise answer here.", "source_page": page_number, "confidence_score": Rate your answer base on context chunks and their scores. The range around between 0.0 and 1.0}}
    Do not include markdown tags like ```json.
    """

    if error:
        system_prompt += f"\n\nWARNING: Your previous attempt failed. Fix this error: {error}"

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "Context:\n{context}\n\n-----\n\n Base on above context, answer the following question: {query}")
    ])

    chain = prompt | llm

    response = chain.invoke({"context": context_str, "query": query})
    print("llm time:", time.time() - start)
    return {"generation": response.content[0].get("text", "").strip()}

def audit_node(state: GraphState):
    """Checking JSON output"""
    print("--- NODE 3: AUDITOR ---")
    generation = state["generation"]
    retries = state.get("retries", 0)
    
    try:
        clean_json = generation.replace("```json", "").replace("```", "").strip()
        parsed_data = json.loads(clean_json)
        
        required_keys = {"answer", "source_page", "confidence_score"}
        if not required_keys.issubset(parsed_data.keys()):
            raise ValueError(f"Missing required fields. Output must contain: {required_keys}")
            
        print("Audit: PASS")
        return {"error": None, "generation": clean_json}
        
    except Exception as e:
        print(f"Audit: FAIL - {str(e)}")
        return {"error": str(e), "retries": retries + 1}

def route_audit(state: GraphState):
    """Quyết định kết thúc hay yêu cầu LLM thử lại."""
    error = state.get("error")
    retries = state.get("retries", 0)
    
    if error is None:
        return "end" 
    elif retries < 3:
        return "retry" 
    else:
        print("Max retries reached. Failing gracefully.")
        return "end"

# Init workflow
workflow = StateGraph(GraphState)

# Define nodes
workflow.add_node("retriever", retrieve_node)
workflow.add_node("generator", generate_node)
workflow.add_node("auditor", audit_node)

workflow.set_entry_point("retriever")

workflow.add_edge("retriever", "generator")
workflow.add_edge("generator", "auditor")

workflow.add_conditional_edges(
    "auditor",
    route_audit,
    {
        "retry": "generator",
        "end": END
    }
)

app_graph = workflow.compile()

api = FastAPI()

@api.post("/chat")
async def chat(user_id: str, message: str):
    result = app_graph.invoke(
        {"query": message, "retries": 0}, 
        config={"configurable": {"thread_id": user_id}}
    )
    
    return {
        "user_id": user_id,
        "response": json.loads(result.get("generation", "{}"))
    }

@api.get("/")
async def root():
    return {"message": "Server is running!"}

handler = Mangum(api)