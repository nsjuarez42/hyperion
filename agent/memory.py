"""Conversation memory per user_id, kept in the running process.

The evaluators run one container with no volume, so anything on disk would be
lost the same way; keeping it behind these functions means the storage can be
swapped without touching the rest of the agent.
"""

import asyncio

from langchain_core.messages import AIMessage, HumanMessage

from agent.config import MAX_HISTORY_MESSAGES, MAX_SESSIONS

sessions: dict[str, list] = {}
locks: dict[str, asyncio.Lock] = {}


def session_lock(user_id: str) -> asyncio.Lock:
    """One lock per user, so two quick messages cannot interleave their turns."""
    lock = locks.get(user_id)
    if lock is None:
        lock = asyncio.Lock()
        locks[user_id] = lock
    return lock


def get_history(user_id: str) -> list:
    if user_id in sessions:
        return sessions[user_id]
    return []


def save_turn(user_id: str, user_message: str, ai_message: str):
    """Store one exchange, keep the last whole turns, evict the oldest users."""
    if user_id not in sessions:
        sessions[user_id] = []
    sessions[user_id].append(HumanMessage(content=user_message))
    sessions[user_id].append(AIMessage(content=ai_message))
    sessions[user_id] = sessions[user_id][-MAX_HISTORY_MESSAGES:]
    while len(sessions) > MAX_SESSIONS:
        oldest = next(iter(sessions))
        if oldest == user_id:
            break
        del sessions[oldest]
        locks.pop(oldest, None)
