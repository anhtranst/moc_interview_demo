from dataclasses import dataclass, field


@dataclass
class InterviewData:
    """Shared state that persists across all interview agents via AgentSession.userdata."""

    interview_code: str | None = None
    started_at: float | None = None
    candidate_name: str | None = None
    introduction_summary: str | None = None
    transition_source: str | None = None  # "tool" or "fallback"

    # CV-related fields populated at session start
    cv_text: str | None = None
    stt_keywords: list[tuple[str, float]] = field(default_factory=list)

    # Experience-stage tracking
    experience_topics_discussed: int = 0
