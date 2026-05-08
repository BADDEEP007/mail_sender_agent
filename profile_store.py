"""
Profile Processing Module
- Loads profile information from text files instead of PDFs
- Chunks text content
- Embeds with HuggingFace sentence-transformers
- Stores in FAISS
- Returns a retriever for profile-based context
"""
import os
import warnings
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from config import FAISS_INDEX_DIR, CHUNK_SIZE, CHUNK_OVERLAP, RETRIEVER_K
from logger import logger

# Suppress warnings
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)
os.environ["TOKENIZERS_PARALLELISM"] = "false"

EMBED_MODEL = "all-MiniLM-L6-v2"  # fast, lightweight, good quality
PROFILE_FILE = "profile.txt"  # Default profile file name


def _get_embeddings() -> HuggingFaceEmbeddings:
    return HuggingFaceEmbeddings(
        model_name=EMBED_MODEL,
        encode_kwargs={'normalize_embeddings': True}
    )


def load_profile(profile_path: str = None) -> list[Document]:
    """Load profile information from a text file."""
    if profile_path is None:
        profile_path = PROFILE_FILE
    
    if not os.path.exists(profile_path):
        raise FileNotFoundError(f"Profile file not found: {profile_path}")
    
    logger.info(f"Loading profile from: {profile_path}")
    
    with open(profile_path, 'r', encoding='utf-8') as f:
        content = f.read().strip()
    
    if not content:
        raise ValueError(f"Profile file is empty: {profile_path}")
    
    # Create a document from the profile content
    doc = Document(
        page_content=content,
        metadata={"source": profile_path, "type": "profile"}
    )
    
    logger.info(f"Loaded profile: {len(content)} characters")
    return [doc]


def build_vector_store(profile_path: str = None, force_rebuild: bool = False) -> FAISS:
    """Build or load FAISS index from profile text."""
    embeddings = _get_embeddings()
    
    # Create a unique index path based on profile file
    if profile_path is None:
        profile_path = PROFILE_FILE
    
    profile_name = os.path.splitext(os.path.basename(profile_path))[0]
    index_dir = os.path.join(FAISS_INDEX_DIR, f"profile_{profile_name}")
    
    if os.path.exists(index_dir) and not force_rebuild:
        logger.info(f"Loading existing FAISS index from {index_dir}...")
        return FAISS.load_local(index_dir, embeddings, allow_dangerous_deserialization=True)
    
    logger.info(f"Building new FAISS index from profile: {profile_path}")
    docs = load_profile(profile_path)
    
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ".", " "]
    )
    chunks = splitter.split_documents(docs)
    logger.info(f"Split profile into {len(chunks)} chunks")
    
    store = FAISS.from_documents(chunks, embeddings)
    os.makedirs(index_dir, exist_ok=True)
    store.save_local(index_dir)
    logger.info(f"FAISS index saved to {index_dir}")
    return store


def get_retriever(profile_path: str = None, force_rebuild: bool = False):
    """Return a retriever configured for profile-based context fetching."""
    store = build_vector_store(profile_path, force_rebuild)
    return store.as_retriever(search_kwargs={"k": RETRIEVER_K})


def retrieve_context(role: str, company: str, retriever) -> str:
    """
    Fetch relevant profile sections for a given role and company.
    Focus on projects, achievements, and measurable outcomes.
    """
    # Build a more specific query that asks for relevant experience
    query = f"""
    Experience, projects, and achievements relevant to {role} position at {company}.
    Include: project names, technologies used, measurable results, 
    specific systems built, technical challenges solved, and relevant skills.
    """
    
    docs = retriever.invoke(query)
    
    # Join with clear separation
    context_parts = []
    for i, doc in enumerate(docs, 1):
        content = doc.page_content.strip()
        context_parts.append(f"[Profile Section {i}]\n{content}")
    
    context = "\n\n".join(context_parts)
    logger.info(f"Retrieved {len(docs)} context chunks for role: {role} (total {len(context)} chars)")
    return context