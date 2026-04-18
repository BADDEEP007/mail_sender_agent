import os
from dotenv import load_dotenv
from langchain_core.output_parsers import StrOutputParser
load_dotenv()

GROQ_API_KEY    = os.environ.get("groq_key")
EMAIL_USER      = os.environ.get("personal_mail")
EMAIL_PASSWORD  = os.environ.get("personal_mail_app_password")
SMTP_SERVER     = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT       = int(os.getenv("SMTP_PORT", 587))
DRY_RUN         = os.getenv("DRY_RUN", "false").lower() == "true"

RESUMES_DIR     = os.path.join(os.path.dirname(__file__), "data", "Resume")
PROMPTS_DIR     = os.path.join(os.path.dirname(__file__), "prompts")
OUTPUT_DIR      = os.path.join(os.path.dirname(__file__), "output")
LOGS_DIR        = os.path.join(os.path.dirname(__file__), "logs")
FAISS_INDEX_DIR = os.path.join(os.path.dirname(__file__), "data", "faiss_index")

CHUNK_SIZE       = 500
CHUNK_OVERLAP    = 50
RETRIEVER_K      = 5  # Increased from 3 to get more project examples
LLM_MODEL        = "llama-3.1-8b-instant"   # fast + free on Groq
LLM_TEMPERATURE  = 0.7
EMAIL_RATE_LIMIT = 2   # seconds between sends
EMAIL_MAX_RETRY  = 3
ENABLE_COMPANY_SEARCH = os.getenv("ENABLE_COMPANY_SEARCH", "true").lower() == "true"
PARSER = StrOutputParser()