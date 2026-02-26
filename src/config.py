# Time in seconds before the fallback timer forces a transition
# from IntroductionAgent to PastExperienceAgent
INTRODUCTION_FALLBACK_TIMEOUT: float = 120.0

# Hard ceiling on LLM response length (tokens). ~150 tokens ≈ 2-3 short sentences.
MAX_COMPLETION_TOKENS: int = 150

# Minimum silence (seconds) before the agent treats the user's turn as complete.
# 3s covers natural thinking pauses between sentences in an interview setting.
MIN_ENDPOINTING_DELAY: float = 3.0

# Maximum wait (seconds) before forcing the turn to end regardless of speech.
# 6s accommodates longer thinking pauses typical in interviews.
MAX_ENDPOINTING_DELAY: float = 6.0
