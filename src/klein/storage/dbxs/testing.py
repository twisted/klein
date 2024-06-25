"""
Testing support for L{klein.storage.dbxs}.

L{MemoryPool} creates a synchronous, in-memory SQLite database that can be used
for testing anything that needs an
L{klein.storage.dbxs.dbapi_async.AsyncConnectable}.
"""

from ._testing import MemoryPool, immediateTest


__all__ = [
    "MemoryPool",
    "immediateTest",
]
