# -*- test-case-name: klein.test.test_request -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Hypothesis strategies.
"""

from string import ascii_letters
from typing import Callable, Optional, Text, TypeVar

from hypothesis.strategies import characters, composite, lists, text

Optional, Text  # Silence linter


__all__ = ()


settings.register_profile(
    "ci", settings(suppress_health_check=[HealthCheck.too_slow])
)
if getenv("CI") == "true":
    settings.load_profile("ci")


T = TypeVar('T')
DrawCallable = Callable[[Callable[..., T]], T]


@composite
def ascii_text(draw, min_size=None, max_size=None):
    # type: (DrawCallable, Optional[int], Optional[int]) -> Text
    """
    A strategy which generates ASCII-encodable text.

    @param min_size: The minimum number of characters in the text.
        C{None} is treated as C{0}.

    @param max_size: The maximum number of characters in the text.
        Use C{None} for an unbounded size.
    """
    return draw(text(
        min_size=min_size, max_size=max_size, alphabet=ascii_letters
    ))


@composite
def latin1_text(draw, min_size=None, max_size=None):
    # type: (DrawCallable, Optional[int], Optional[int]) -> Text
    """
    A strategy which generates ISO-8859-1-encodable text.

    @param min_size: The minimum number of characters in the text.
        C{None} is treated as C{0}.

    @param max_size: The maximum number of characters in the text.
        Use C{None} for an unbounded size.
    """
    return u"".join(draw(lists(
        characters(max_codepoint=255),
        min_size=min_size, max_size=max_size,
    )))
