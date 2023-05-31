"""
Since we support a range of Python and Mypy versions where certain features are
available across L{typing} and L{typing_extensions}, we put those aliases here
to avoid repeating conditional import logic.
"""
import sys


if sys.version_info > (3, 10):
    from typing import Concatenate, ParamSpec, Protocol
else:
    from typing_extensions import Concatenate, ParamSpec, Protocol


__all__ = [
    "Protocol",
    "ParamSpec",
    "Concatenate",
]
