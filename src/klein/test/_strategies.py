# Copyright (c) 2017-2018. See LICENSE for details.

"""
Hypothesis strategies.
"""

from csv import reader as csvReader
from os.path import dirname, join
from string import ascii_letters, digits
from sys import maxunicode
from typing import Callable, Optional, Text, TypeVar

from hyperlink import URL

from hypothesis import HealthCheck, settings
from hypothesis.strategies import (
    characters, composite, integers, iterables, lists, sampled_from, text
)

from twisted.python.compat import _PY3, unicode

Optional, Text  # Silence linter


__all__ = ()


settings.register_profile(
    "patience", settings(suppress_health_check=[HealthCheck.too_slow])
)
settings.load_profile("patience")


T = TypeVar('T')
DrawCallable = Callable[[Callable[..., T]], T]


if _PY3:
    unichr = chr


def idna_characters():  # pragma: no cover
    # type: () -> str
    """
    Returns a string containing IDNA characters.
    """
    global _idnaCharacters

    if _idnaCharacters is None:
        result = []

        # Data source "IDNA Derived Properties":
        # https://www.iana.org/assignments/idna-tables-6.3.0/
        #   idna-tables-6.3.0.xhtml#idna-tables-properties
        dataFileName = join(dirname(__file__), "idna-tables-properties.csv")
        with open(dataFileName) as dataFile:
            reader = csvReader(dataFile, delimiter=",")
            next(reader)  # Skip header row
            for row in reader:
                codes, prop, description = row

                if prop != "PVALID":
                    # CONTEXTO or CONTEXTJ are also allowed, but they come with
                    # rules, so we're punting on those here.
                    # See: https://tools.ietf.org/html/rfc5892
                    continue

                startEnd = row[0].split("-", 1)
                if len(startEnd) == 1:
                    # No end of range given; use start
                    startEnd.append(startEnd[0])
                start, end = (int(i, 16) for i in startEnd)

                for i in range(start, end + 1):
                    if i > maxunicode:
                        break
                    result.append(unichr(i))

        _idnaCharacters = u"".join(result)

    return _idnaCharacters

_idnaCharacters = None  # type: Optional[str]


@composite
def ascii_text(draw, min_size=None, max_size=None):  # pragma: no cover
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


@composite  # pragma: no cover
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
def idna_text(draw, min_size=None, max_size=None):  # pragma: no cover
    # type: (DrawCallable, Optional[int], Optional[int]) -> Text
    """
    A strategy which generates IDNA-encodable text.

    @param min_size: The minimum number of characters in the text.
        C{None} is treated as C{0}.

    @param max_size: The maximum number of characters in the text.
        Use C{None} for an unbounded size.
    """
    return draw(text(
        min_size=min_size, max_size=max_size, alphabet=idna_characters()
    ))


@composite
def port_numbers(draw, allow_zero=False):  # pragma: no cover
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
def hostname_labels(draw, allow_idn=True):  # pragma: no cover
    # type: (DrawCallable, bool) -> Text
    """
    A strategy which generates host name labels.

    @param allow_idn: Whether to allow non-ASCII characters as allowed by
        internationalized domain names (IDNs).
    """
    if allow_idn:
        label = draw(idna_text(min_size=1, max_size=63))
    else:
        label = draw(text(
            min_size=1, max_size=63,
            alphabet=unicode(ascii_letters + digits + u"-")
        ))

    return label


@composite
def hostnames(
    draw, allow_leading_digit=True, allow_idn=True
):  # pragma: no cover
    # type: (DrawCallable, bool, bool) -> Text
    """
    A strategy which generates host names.

    @param allow_leading_digit: Whether to allow a leading digit in host names;
        they were not allowed prior to RFC 1123.

    @param allow_idn: Whether to allow non-ASCII characters as allowed by
        internationalized domain names (IDNs).
    """
    labels = draw(
        lists(
            hostname_labels(allow_idn=allow_idn),
            min_size=1, max_size=5, average_size=2
        )
        .filter(lambda ls: sum(len(l) for l in ls) + len(ls) - 1 <= 252)
    )

    name = u".".join(labels)

    return name


_path_characters = tuple(
    unichr(i)
    for i in range(maxunicode) if i not in (ord(c) for c in "#/?")
)

@composite
def path_segments(draw):  # pragma: no cover
    # type: (DrawCallable) -> Text
    """
    A strategy which generates URL path segments.
    """
    return draw(
        iterables(
            text(min_size=1, alphabet=_path_characters),
            max_size=10, average_size=3,
        )
    )


@composite
def http_urls(draw):  # pragma: no cover
    # type: (DrawCallable) -> URL
    """
    A strategy which generates (human-friendly, unicode) IRI-form L{URL}s.
    Call the C{asURI} method on each URL to get a (network-friendly, ASCII)
    URI.
    """
    port = draw(port_numbers(allow_zero=True))
    host = draw(hostnames())
    path = draw(path_segments())

    if port == 0:
        port = None

    args = dict(
        scheme=draw(sampled_from((u"http", u"https"))),
        host=host, port=port, path=path,
    )

    return URL(**args)
