"""Tests cover the code that does not need the LLM or the IDE: routing rules,
parsing, templates, confirmation, messages and keyword retrieval.

An empty API_KEY is set before the agent is imported (load_dotenv never
overrides a variable that is already set), so no test can reach the LLM or
embedding server even if a real .env is present.
"""

import os
import sys
from pathlib import Path

os.environ["API_KEY"] = ""
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
