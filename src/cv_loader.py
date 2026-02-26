"""Utilities for loading and parsing candidate CVs."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from pypdf import PdfReader

logger = logging.getLogger("mock-interview")

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# Prompt sent to the LLM to extract structured metadata from CV text.
_EXTRACTION_PROMPT = """\
You are given the text of a candidate's CV/resume. Extract the following as JSON:

{
  "candidate_name": "Full name of the candidate",
  "keywords": [
    ["phrase", boost],
    ...
  ]
}

Rules for keywords:
- Include the candidate's full name and any name variations (e.g. "Anh Tran", "Antoine Tran")
- Include company names, job titles, university/school names
- Include technical skills, programming languages, frameworks, and tools
- Include project names and certifications
- Each keyword is a [phrase, boost] pair where boost is 10.0-25.0 (higher = more important for speech recognition)
- Use boost 25.0 for the candidate's name, 20.0 for companies/universities, 15.0 for technical terms
- Return 15-30 keywords maximum

Respond with ONLY the JSON object, no other text.

CV text:
"""


@dataclass
class CvMetadata:
    """Structured metadata extracted from a CV by the LLM."""

    candidate_name: str | None = None
    keywords: list[tuple[str, float]] = field(default_factory=list)


def load_cv_text(interview_code: str) -> str | None:
    """Load and extract text from the first PDF in data/{code}/cv/.

    Returns the extracted text, or None if no PDF is found.
    """
    cv_dir = _DATA_DIR / interview_code / "cv"
    if not cv_dir.is_dir():
        return None

    pdf_files = sorted(cv_dir.glob("*.pdf"))
    if not pdf_files:
        return None

    pdf_path = pdf_files[0]
    logger.info("Loading CV from %s", pdf_path)

    try:
        reader = PdfReader(pdf_path)
        pages = [page.extract_text() or "" for page in reader.pages]
        text = "\n\n".join(pages).strip()
        if not text:
            logger.warning("CV PDF has no extractable text: %s", pdf_path)
            return None
        return text
    except Exception:
        logger.exception("Failed to read CV PDF: %s", pdf_path)
        return None


async def extract_cv_metadata(cv_text: str, llm: object) -> CvMetadata:
    """Call the LLM to extract candidate name and STT keywords from CV text.

    Args:
        cv_text: Raw text extracted from the CV PDF.
        llm: An openai.LLM instance (or compatible) to use for extraction.
    """
    from livekit.agents.llm import ChatContext

    chat_ctx = ChatContext.empty()
    chat_ctx.add_message(role="user", content=_EXTRACTION_PROMPT + cv_text)

    try:
        stream = llm.chat(chat_ctx=chat_ctx)
        response_text = ""
        async for chunk in stream:
            if chunk.delta and chunk.delta.content:
                response_text += chunk.delta.content

        # Parse JSON from response
        data = json.loads(response_text)
        candidate_name = data.get("candidate_name")
        raw_keywords = data.get("keywords", [])
        keywords = [(str(k[0]), float(k[1])) for k in raw_keywords if len(k) >= 2]

        logger.info(
            "CV metadata extracted: name=%s, %d keywords",
            candidate_name,
            len(keywords),
        )
        return CvMetadata(candidate_name=candidate_name, keywords=keywords)

    except Exception:
        logger.exception("Failed to extract CV metadata via LLM")
        return CvMetadata()
