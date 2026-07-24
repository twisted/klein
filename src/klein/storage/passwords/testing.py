# -*- test-case-name: klein.storage.passwords.test.test_passwords -*-
"""
Unit testing support for L{klein.storage.passwords}.

In production, password hashing needs to be slow enough that it requires
delgation to alternate threads, and, obviously, deterministic.  These testing
facilities present the same interface, but are fast so as not to slow down your
tests; for safety, they are I{not} repeatable, generating per-session state and
providing no API to serialize it, so as to avoid accidentally relying on it in
production.
"""

from ._testing import engineForTesting, hashUpgradeCount


__all__ = [
    "engineForTesting",
    "hashUpgradeCount",
]
