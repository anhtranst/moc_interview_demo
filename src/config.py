# Time in seconds before the fallback timer forces a transition
# from IntroductionAgent to PastExperienceAgent
INTRODUCTION_FALLBACK_TIMEOUT: float = 120.0

# Hard ceiling on LLM response length (tokens). ~150 tokens ≈ 2-3 short sentences.
MAX_COMPLETION_TOKENS: int = 150

# Keywords for deterministic command detection (matched case-insensitively).
STOP_KEYWORDS: set[str] = {"stop", "quit", "end interview", "exit"}
PAUSE_KEYWORDS: set[str] = {"pause", "wait", "hold on", "one moment", "give me a moment"}
RESUME_KEYWORDS: set[str] = {"resume", "continue", "go on", "go ahead", "i'm ready", "im ready"}
