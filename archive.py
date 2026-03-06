from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate
import os
import shutil
from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()
GEMINI_API_KEY=os.getenv("GEMINI_API_KEY")
DB_DIR = "./db"

class AnswerSchema(BaseModel):
    answer: str = Field(description="Answer to the question")
    source_page: str = Field(description="Page number where the answer was found")
    confidence_score: str = Field(description="Confidence score is the score in context, around between 0 and 1")

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size = 500,
    chunk_overlap = 100,
    add_start_index = True
)

embedding = GoogleGenerativeAIEmbeddings(
    model="gemini-embedding-001",
    api_key=GEMINI_API_KEY
    )

if os.path.exists(DB_DIR):
    shutil.rmtree(DB_DIR)

vector_store = Chroma(
    collection_name="policy_database",
    embedding_function=embedding,
    persist_directory=DB_DIR
)

loader = PyPDFLoader("./data/policy.pdf")
documents = loader.load()
all_splits = text_splitter.split_documents(documents)
if vector_store._collection.count() == 0:
    vector_store.add_documents(documents)

def model(context_text, query_text):
    PROMPT_TEMPLATE = """
You are a helpful assitant, can speak any language and helping new employee in understanding the company policy:
{context}
----
If the answer is not in the context, say you don't know.
Answer the question base on above context: {query}"""
    prompt_template = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
    prompt = prompt_template.format(context=context_text, query=query_text)

    llm = ChatGoogleGenerativeAI(
        model="gemini-3-pro-preview",
        api_key=GEMINI_API_KEY
    )

    structured_llm = llm.with_structured_output(AnswerSchema)

    response = structured_llm.invoke(prompt)

    return response.model_dump()

while True:
    query_text = input()
    docs = vector_store.similarity_search_with_score(query_text, k=3)
    context_text = "\n\n----\n\n".join(
        [f"Page {doc.metadata.get('page', 'unknown')}, (score={score:.3f}):\n{doc.page_content}" 
         for doc, score in docs if score >= 0.52])
    
    with open('./context.txt', "w") as f: print(context_text, file=f)
    print(model(context_text, query_text))