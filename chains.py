"""
LangChain chains for email and referral generation.
Prompts loaded dynamically from prompts/ directory.
Uses Groq ChatGroq as the LLM backend.
"""
import os
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import Runnable
from config import PROMPTS_DIR, LLM_MODEL, LLM_TEMPERATURE, GROQ_API_KEY, PARSER
from logger import logger


def _load_prompt(filename: str) -> str:
    path = os.path.join(PROMPTS_DIR, filename)
    with open(path, "r") as f:
        return f.read()


def _get_llm() -> ChatGroq:
    return ChatGroq(
        model=LLM_MODEL,
        temperature=LLM_TEMPERATURE,
        groq_api_key=GROQ_API_KEY
    )


def build_cold_email_chain() -> Runnable:
    template = _load_prompt("cold_email.txt")
    prompt = PromptTemplate(
        input_variables=["name", "role", "company", "company_context", "resume_context"],
        template=template
    )
    return  prompt| _get_llm() |PARSER

def build_subject_chain() -> Runnable:
    template = _load_prompt("subject_line.txt")
    prompt = PromptTemplate(
        input_variables=["name", "role", "company"],
        template=template
    )
    return  prompt| _get_llm() |PARSER


def build_referral_chain() -> Runnable:
    template = _load_prompt("referral.txt")
    prompt = PromptTemplate(
        input_variables=["name", "role", "company", "relationship"],
        template=template
    )
    return  prompt| _get_llm() |PARSER


def generate_cold_email(name: str, role: str, company: str, company_context: str, resume_context: str) -> str:
    chain = build_cold_email_chain()
    result = chain.invoke({
        "name": name,
        "role": role,
        "company": company,
        "company_context": company_context,
        "resume_context": resume_context
    })
    body = result.strip()
    logger.info(f"Cold email generated for {name} @ {company} ({len(body.split())} words)")
    return body


def generate_subject_lines(name: str, role: str, company: str) -> list[str]:
    chain = build_subject_chain()
    result = chain.invoke({"name": name, "role": role, "company": company})
    lines = [l.strip() for l in result.strip().splitlines() if l.strip()][:3]
    logger.info(f"Subject lines generated: {lines}")
    return lines


def generate_referral(name: str, role: str, company: str, relationship: str) -> str:
    if relationship not in ("stranger", "alumni", "mutual"):
        raise ValueError(f"relationship must be stranger/alumni/mutual, got: {relationship}")
    chain = build_referral_chain()
    result = chain.invoke({
        "name": name,
        "role": role,
        "company": company,
        "relationship": relationship
    })
    msg = result.strip()
    logger.info(f"Referral message generated ({relationship}) for {company} ({len(msg.split())} words)")
    return msg
