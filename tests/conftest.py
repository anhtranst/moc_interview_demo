import logging
import sys
from pathlib import Path

import pytest

# Add livekit_agents test utilities to sys.path so we can import fake_session, fake_llm, etc.
_livekit_tests_dir = str(Path(__file__).resolve().parent.parent.parent / "livekit_agents" / "tests")
if _livekit_tests_dir not in sys.path:
    sys.path.insert(0, _livekit_tests_dir)

# Add the project root so `src.*` imports work
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


@pytest.fixture(autouse=True)
def configure_test():
    """Silence noisy loggers during tests."""
    logging.getLogger("livekit").setLevel(logging.WARNING)
    logging.getLogger("mock-interview").setLevel(logging.WARNING)
