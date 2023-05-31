"""
Since we support a range of Python and Mypy versions where certain features are
available across L{typing} and L{typing_extensions}, we put those aliases here
to avoid repeating conditional import logic.
"""
import sys


if sys.version_info > (3, 10):
    from typing import Concatenate, ParamSpec, Protocol
else:
    # PyPy 3.9 seems to have a bonus runtime check for Protocol's generic
    # arguments all being TypeVars, so lie to it about ParamSpec.
    from typing import TYPE_CHECKING

    from typing_extensions import Concatenate, Protocol

    if TYPE_CHECKING:
        from typing_extensions import ParamSpec
    else:
        from platform import python_implementation

        if python_implementation() == "PyPy":
            from typing import TypeVar as ParamSpec
        else:
            from typing_extensions import ParamSpec


__all__ = [
    "Protocol",
    "ParamSpec",
    "Concatenate",
]
