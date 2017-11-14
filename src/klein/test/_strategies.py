# Copyright (c) 2017-2018. See LICENSE for details.

"""
Hypothesis strategies.
"""

from string import ascii_letters
from typing import Callable, Optional, Text, TypeVar

from hypothesis import HealthCheck, settings
from hypothesis.strategies import characters, composite, lists, text

Optional, Text  # Silence linter


__all__ = ()


settings.register_profile(
    "patience", settings(suppress_health_check=[HealthCheck.too_slow])
)
settings.load_profile("patience")


T = TypeVar('T')
DrawCallable = Callable[[Callable[..., T]], T]


# Note this may be incorrect (most likely: incomplete), but it's at least OK
# for generating IDNA test data.
IDNA_CHARACTER_CATEGORIES = (
    "Lu", "Ll", "Lt",                          # cased letters
    "Mn", "Mc", "Me",                          # marks
    "Nd", "Nl", "No",                          # numbers
    "Pc", "Pd", "Ps", "Pe", "Pe", "Pf", "Po",  # punctuation
    "Sm", "Sc", "Sk", "So",                    # symbols
)


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
