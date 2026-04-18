"""
Resume Processing Module
- Loads PDFs from data/resumes/
- Chunks text
- Embeds with HuggingFace sentence-transformers (local, free)
- Stores in FAISS
- Returns a retriever
Note: Groq has no embeddings API — using local sentence-transformers instead.
"""
import os
import warnings
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from config import RESUMES_DIR, FAISS_INDEX_DIR, CHUNK_SIZE, CHUNK_OVERLAP, RETRIEVER_K
from logger import logger

# Suppress warnings
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)
os.environ["TOKENIZERS_PARALLELISM"] = "false"

EMBED_MODEL = "all-MiniLM-L6-v2"  # fast, lightweight, good quality


def _get_embeddings() -> HuggingFaceEmbeddings:
    return HuggingFaceEmbeddings(
        model_name=EMBED_MODEL,
        encode_kwargs={'normalize_embeddings': True, }
    )


def load_resumes() -> list:
    """Load all PDFs from the resumes directory."""
    docs = []
    if not os.path.exists(RESUMES_DIR):
        raise FileNotFoundError(f"Resumes directory not found: {RESUMES_DIR}")

    pdf_files = [f for f in os.listdir(RESUMES_DIR) if f.endswith(".pdf")]
    if not pdf_files:
        raise FileNotFoundError(f"No PDF files found in {RESUMES_DIR}")

    for pdf in pdf_files:
        path = os.path.join(RESUMES_DIR, pdf)
        logger.info(f"Loading resume: {pdf}")
        loader = PyPDFLoader(path)
        docs.extend(loader.load())

    logger.info(f"Loaded {len(docs)} pages from {len(pdf_files)} resume(s)")
    return docs


def build_vector_store(force_rebuild: bool = False) -> FAISS:
    """Build or load FAISS index from resumes."""
    embeddings = _get_embeddings()

    if os.path.exists(FAISS_INDEX_DIR) and not force_rebuild:
        logger.info("Loading existing FAISS index...")
        return FAISS.load_local(FAISS_INDEX_DIR, embeddings, allow_dangerous_deserialization=True)

    logger.info("Building new FAISS index from resumes...")
    docs = load_resumes()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ".", " "]
    )
    chunks = splitter.split_documents(docs)
    logger.info(f"Split into {len(chunks)} chunks")

    store = FAISS.from_documents(chunks, embeddings)
    os.makedirs(FAISS_INDEX_DIR, exist_ok=True)
    store.save_local(FAISS_INDEX_DIR)
    logger.info(f"FAISS index saved to {FAISS_INDEX_DIR}")
    return store


def get_retriever(force_rebuild: bool = False):
    """Return a retriever configured for role-based context fetching."""
    store = build_vector_store(force_rebuild)
    return store.as_retriever(search_kwargs={"k": RETRIEVER_K})


def retrieve_context(role: str, company: str, retriever) -> str:
    """
    Fetch relevant resume sections for a given role and company.
    Focus on projects, achievements, and measurable outcomes.
    """
    # Build a more specific query that asks for projects and achievements
    query = f"""
    Projects and achievements relevant to {role} position at {company}.
    Include: project names, technologies used, measurable results (users, accuracy, performance),
    specific systems built, and technical challenges solved.
    """
    
    docs = retriever.invoke(query)
    
    # Join with clear separation
    context_parts = []
    for i, doc in enumerate(docs, 1):
        content = doc.page_content.strip()
        context_parts.append(f"[Resume Section {i}]\n{content}")
    
    context = "\n\n".join(context_parts)
    logger.info(f"Retrieved {len(docs)} context chunks for role: {role} (total {len(context)} chars)")
    return context
