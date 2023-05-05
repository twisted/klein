"""
Since we support a range of Python and Mypy versions where certain features are
available across L{typing} and L{typing_extensions}, we put those aliases here
to avoid repeating conditional import logic.
"""

from typing import TYPE_CHECKING


try:
    from typing import Protocol
except ImportError:
    if not TYPE_CHECKING:
        from typing_extensions import Protocol
try:
    from typing import ParamSpec
except ImportError:
    if not TYPE_CHECKING:
        from typing_extensions import ParamSpec

__all__ = [
    "Protocol",
    "ParamSpec",
]
