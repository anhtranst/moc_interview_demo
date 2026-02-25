# Time in seconds before the fallback timer forces a transition
# from IntroductionAgent to PastExperienceAgent
INTRODUCTION_FALLBACK_TIMEOUT: float = 120.0

# Hard ceiling on LLM response length (tokens). ~150 tokens ≈ 2-3 short sentences.
MAX_COMPLETION_TOKENS: int = 150
