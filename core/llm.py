"""
Gemini 2.5 Flash LLM client with robust rate-limit handling.
- Auto-retry with exponential backoff on 429 errors
- Single cached instance to minimize API calls
- rate_limited_invoke() wraps all calls with sleep+retry logic
"""
from __future__ import annotations
import json
import os
import re
import time
from functools import lru_cache
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

# Streamlit Cloud: load secrets into os.environ if not already set by .env
try:
    import streamlit as st
    for _key in ["GOOGLE_API_KEY", "SERPAPI_KEY", "TAVILY_API_KEY", "FIRECRAWL_API_KEY"]:
        if not os.getenv(_key) and hasattr(st, "secrets") and _key in st.secrets:
            os.environ[_key] = st.secrets[_key]
except Exception:
    pass



import google.generativeai as genai
try:
    genai.configure(transport="rest")
except Exception:
    pass

@lru_cache(maxsize=4)
def _make_llm(temperature: float) -> ChatGoogleGenerativeAI:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY not set in .env file")
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=api_key,
        temperature=temperature,
        max_retries=2,
        timeout=45.0,
    )


def get_llm(temperature: float = 0.3) -> ChatGoogleGenerativeAI:
    """General-purpose Gemini 2.5 Flash instance."""
    return _make_llm(temperature)


def get_creative_llm() -> ChatGoogleGenerativeAI:
    """High-creativity LLM for insight generation (Agent 6)."""
    return _make_llm(0.7)


def get_precise_llm() -> ChatGoogleGenerativeAI:
    """Low-temperature LLM for classification & ranking (Agents 5, 7)."""
    return _make_llm(0.1)


import socket

def is_domain_reachable(domain: str) -> bool:
    """Check if a domain is resolvable to prevent long OS-level connection hangs."""
    try:
        socket.gethostbyname(domain)
        return True
    except socket.gaierror:
        return False

def rate_limited_invoke(llm, messages: list, max_retries: int = 5) -> str:
    """
    Invoke LLM with Groq API routing fallback if GROQ_API_KEY is present,
    otherwise falls back to Google Gemini with exponential backoff.
    """
    import os
    import time
    import requests

    groq_key = os.getenv("GROQ_API_KEY")
    if groq_key and groq_key.strip():
        # Convert LangChain messages structure to Groq/OpenAI format
        groq_messages = []
        for msg in messages:
            if isinstance(msg, tuple):
                role, content = msg
                role_name = "user" if role in ["human", "user"] else "system" if role in ["system"] else "assistant"
                groq_messages.append({"role": role_name, "content": content})
            elif hasattr(msg, "content"):
                role_name = "user" if "Human" in type(msg).__name__ else "system" if "System" in type(msg).__name__ else "assistant"
                groq_messages.append({"role": role_name, "content": msg.content})
            else:
                groq_messages.append({"role": "user", "content": str(msg)})
                
        payload = {
            "model": "llama-3.1-8b-instant",
            "messages": groq_messages,
            "temperature": 0.1,
        }
        
        # Enable structured JSON parsing if requested in the prompts
        all_text = " ".join(m["content"] for m in groq_messages).lower()
        if "json" in all_text:
            payload["response_format"] = {"type": "json_object"}
            
        headers = {
            "Authorization": f"Bearer {groq_key.strip()}",
            "Content-Type": "application/json"
        }
        
        for attempt in range(max_retries):
            try:
                resp = requests.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    json=payload,
                    headers=headers,
                    timeout=20
                )
                if resp.status_code == 200:
                    return resp.json()["choices"][0]["message"]["content"]
                elif resp.status_code == 429:
                    print(f"[Groq] Rate limited (429). Retrying in 2 seconds...")
                    time.sleep(2)
                else:
                    print(f"[Groq] API Error {resp.status_code}: {resp.text[:200]}")
                    break
            except Exception as e:
                print(f"[Groq] Request exception: {e}")
                time.sleep(1)
        print("[Groq] Failsafe: falling back to Gemini API.")

    # Google Gemini Fallback:
    # Quick network check to avoid 2+ minute OS connection retry loops
    if not is_domain_reachable("generativelanguage.googleapis.com"):
        print("[LLM] Network offline: generativelanguage.googleapis.com is unreachable. Skipping.")
        return ""

    delays = [5, 15, 30, 60, 90]  # seconds between retries
    for attempt, delay in enumerate(delays[:max_retries]):
        try:
            response = llm.invoke(messages)
            return response.content
        except Exception as e:
            err = str(e)
            if "429" in err or "RESOURCE_EXHAUSTED" in err or "quota" in err.lower():
                # Extract suggested retry delay from error if present
                retry_match = re.search(r"retry.*?(\d+(?:\.\d+)?)s", err, re.IGNORECASE)
                suggested = float(retry_match.group(1)) if retry_match else delay
                wait = min(max(suggested + 2, delay), 90)
                print(f"[LLM] Rate limit hit (attempt {attempt+1}/{max_retries}). Waiting {wait:.0f}s...")
                time.sleep(wait)
            else:
                print(f"[LLM] Error: {err[:120]}")
                return ""
    return ""


def parse_json_safely(text: str) -> dict | list:
    """
    Extracts JSON from LLM output even if wrapped in markdown code fences.
    Returns empty dict on parse failure.
    """
    # Strip markdown fences
    cleaned = re.sub(r"```(?:json)?\s*", "", text or "").replace("```", "").strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Try to find JSON object/array within the text
        match = re.search(r"(\[.*\]|\{.*\})", cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
    return {}
