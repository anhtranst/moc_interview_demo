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

# ---------------------------------------------------------------------------
# Experience stage timing
# ---------------------------------------------------------------------------

# Total time budget for the past-experience stage (seconds).
EXPERIENCE_STAGE_TIMEOUT: float = 180.0

# Fraction of EXPERIENCE_STAGE_TIMEOUT at which the "anything else?" closing
# question is injected (0.8 = 80% → 240 s of 300 s).
EXPERIENCE_CLOSING_THRESHOLD: float = 0.8

# Maximum number of CV experiences to ask about before the closing question.
MAX_EXPERIENCE_TOPICS: int = 3

# Maximum candidate turns per experience topic before forcing a move
# to the next topic (1 initial answer + 2 follow-ups = 3 turns).
MAX_TURNS_PER_TOPIC: int = 3

# Extra seconds after EXPERIENCE_STAGE_TIMEOUT to let the candidate finish
# their current turn before the interviewer interrupts politely.
EXPERIENCE_GRACE_PERIOD: float = 30.0
