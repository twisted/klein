"""
In-memory implementations of L{klein.interfaces.ISessionStore} and
L{klein.interfaces.ISimpleAccount}, usable for testing or for ephemeral
applications with static authentication requirements rather than real account
databases.
"""

from ._memory import MemorySessionStore, declareMemoryAuthorizer
from ._memory_users import MemoryAccountStore


__all__ = [
    "declareMemoryAuthorizer",
    "MemorySessionStore",
    "MemoryAccountStore",
]
