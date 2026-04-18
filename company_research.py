"""
Company Research Module
- Searches web for company info using DuckDuckGo (no API key needed)
- Extracts key facts: products, tech stack, recent news, culture
- Returns structured context for email personalization
"""
import logging
from ddgs import DDGS
from logger import logger

# Silence DuckDuckGo logs
logging.getLogger("duckduckgo_search").setLevel(logging.ERROR)


def search_company(company: str, role: str) -> str:
    """
    Search for company information and return relevant context.
    Focus on technical details, products, and engineering challenges.
    
    Args:
        company: Company name
        role: Target role (helps focus the search)
    
    Returns:
        Structured string with company context
    """
    try:
        ddgs = DDGS()
        
        # Search 1: Products and what they build
        query1 = f"{company} products services what they build technology"
        results1 = list(ddgs.text(query1, max_results=3))
        
        # Search 2: Tech stack and engineering
        query2 = f"{company} engineering tech stack architecture how they build"
        results2 = list(ddgs.text(query2, max_results=3))
        
        # Search 3: Recent engineering work or challenges
        query3 = f"{company} engineering blog technical challenges {role}"
        results3 = list(ddgs.text(query3, max_results=2))
        
        # Combine results
        all_results = results1 + results2 + results3
        
        if not all_results:
            logger.warning(f"No search results found for {company}")
            return f"{company} is a technology company working on software solutions."
        
        # Extract snippets with focus on technical details
        snippets = []
        for r in all_results:
            title = r.get("title", "")
            body = r.get("body", "")
            
            # Prioritize results with technical keywords
            technical_keywords = ["api", "backend", "frontend", "database", "cloud", "aws", "kubernetes", 
                                "microservices", "ml", "ai", "scale", "infrastructure", "architecture"]
            
            if body and any(keyword in body.lower() for keyword in technical_keywords):
                snippets.insert(0, f"- {body[:250]}")  # Technical results first
            elif body:
                snippets.append(f"- {body[:250]}")
        
        context = "\n".join(snippets[:6])  # Top 6 snippets
        logger.info(f"Company research completed for {company} ({len(snippets)} snippets, technical focus)")
        return context
        
    except Exception as e:
        logger.error(f"Company search failed for {company}: {e}")
        return f"{company} is a technology company working on software solutions."


def search_company_detailed(company: str) -> dict:
    """
    More structured search returning categorized info.
    
    Returns:
        {
            "products": str,
            "tech_stack": str,
            "recent_news": str,
            "culture": str
        }
    """
    try:
        ddgs = DDGS()
        
        # Products/Services
        products_query = f"{company} main products services what they do"
        products_results = list(ddgs.text(products_query, max_results=2))
        products = " ".join([r.get("body", "")[:150] for r in products_results])
        
        # Tech Stack
        tech_query = f"{company} technology stack engineering tools"
        tech_results = list(ddgs.text(tech_query, max_results=2))
        tech_stack = " ".join([r.get("body", "")[:150] for r in tech_results])
        
        # Recent News
        news_query = f"{company} latest news updates 2026"
        news_results = list(ddgs.text(news_query, max_results=2))
        recent_news = " ".join([r.get("body", "")[:150] for r in news_results])
        
        # Culture
        culture_query = f"{company} company culture engineering team"
        culture_results = list(ddgs.text(culture_query, max_results=2))
        culture = " ".join([r.get("body", "")[:150] for r in culture_results])
        
        logger.info(f"Detailed company research completed for {company}")
        
        return {
            "products": products or "Not found",
            "tech_stack": tech_stack or "Not found",
            "recent_news": recent_news or "Not found",
            "culture": culture or "Not found"
        }
        
    except Exception as e:
        logger.error(f"Detailed company search failed for {company}: {e}")
        return {
            "products": f"{company} products and services",
            "tech_stack": "Technology stack information",
            "recent_news": "Recent company updates",
            "culture": "Company culture and values"
        }
