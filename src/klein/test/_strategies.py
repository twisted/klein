# -*- test-case-name: klein.test.test_request -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Hypothesis strategies.
"""

from os import getenv
from string import ascii_letters, digits
from typing import Callable, Optional, Text, TypeVar

from hyperlink import URL

from hypothesis import HealthCheck, assume, settings
from hypothesis.strategies import (
    characters, composite, integers, iterables, lists, sampled_from, text
)

from twisted.python.compat import unicode

Optional, Text  # Silence linter


__all__ = ()


settings.register_profile(
    "ci", settings(suppress_health_check=[HealthCheck.too_slow])
)
if getenv("CI") == "true":
    settings.load_profile("ci")


T = TypeVar('T')
DrawCallable = Callable[[Callable[..., T]], T]


# Note this may be incorrect (most likely: incomplete), but it's at least OK
# for generating IDNA test data.
IDNA_CHARACTER_CATEGORIES = (
    "Lu", "Ll", "Lt",                    # cased letters
    "Mn", "Mc", "Me",                    # marks
    "Nd", "Nl", "No",                    # nubers
    "Pc", "Pd", "Ps", "Pe", "Pe", "Pf",  # punctuation not Po
    "Sm", "Sc", "Sk", "So",              # symbols not So
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


@composite
def idna_text(draw, min_size=None, max_size=None):
    # type: (DrawCallable, Optional[int], Optional[int]) -> Text
    """
    A strategy which generates IDNA-encodable text.

    @param min_size: The minimum number of characters in the text.
        C{None} is treated as C{0}.

    @param max_size: The maximum number of characters in the text.
        Use C{None} for an unbounded size.
    """
    return u"".join(draw(lists(
        characters(whitelist_categories=IDNA_CHARACTER_CATEGORIES),
        min_size=min_size, max_size=max_size,
    )))


def is_idna_compatible(text, max_length):
    # type: (Text, int) -> bool
    """
    Determine whether some text contains only characters that can be encoded
    as IDNA, and that the encoded text is less than the given maximum length.

    @param text: The text to check.

    @param max_length: The maximum allowed length for the encoded text.
    """
    try:
        idna = text.encode("idna")
    except ValueError:
        return False

    return len(idna) <= max_length


@composite
def port_numbers(draw, allow_zero=False):
    # type: (DrawCallable, bool) -> int
    """
    A strategy which generates port numbers.

    @param allow_zero: Whether to allow port C{0} as a possible value.
    """
    if allow_zero:
        min_value = 0
    else:
        min_value = 1

    return draw(integers(min_value=min_value, max_value=65535))


@composite
def hostname_labels(draw, allow_idn=True):
    # type: (DrawCallable, bool) -> Text
    """
    A strategy which generates host name labels.

    @param allow_idn: Whether to allow non-ASCII characters as allowed by
        internationalized domain names (IDNs).
    """
    if allow_idn:
        label = draw(idna_text(min_size=1, max_size=63))
        assume(is_idna_compatible(label, 63))
    else:
        label = draw(text(
            min_size=1, max_size=63,
            alphabet=unicode(ascii_letters + digits + u"-")
        ))

    return label


@composite
def hostnames(draw, allow_leading_digit=True, allow_idn=True):
    # type: (DrawCallable, bool, bool) -> Text
    """
    A strategy which generates host names.

    @param allow_leading_digit: Whether to allow a leading digit in host names;
        they were not allowed prior to RFC 1123.

    @param allow_idn: Whether to allow non-ASCII characters as allowed by
        internationalized domain names (IDNs).
    """
    labels = draw(lists(
        hostname_labels(allow_idn=allow_idn),
        min_size=1, max_size=5, average_size=2
    ))

    name = u".".join(labels)

    if allow_idn:
        assume(is_idna_compatible(name, 252))
    else:
        assume(len(name) <= 252)

    return name


@composite
def path_segments(draw):
    # type: (DrawCallable) -> Text
    """
    A strategy which generates URL path segments.
    """
    path = draw(iterables(text(min_size=1), max_size=10, average_size=3))
    for reserved in "/?#":
        assume(reserved not in path)
    return path


@composite
def http_urls(draw):
    # type: (DrawCallable) -> URL
    """
    A strategy which generates (human-friendly, unicode) IRI-form L{URL}s.
    Call the C{asURI} method on each URL to get a (network-friendly, ASCII)
    URI.
    """
    port = draw(port_numbers(allow_zero=True))
    if port == 0:
        port = None

    return URL(
        scheme=draw(sampled_from((u"http", u"https"))),
        host=draw(hostnames()), port=port, path=draw(path_segments()),
    )
