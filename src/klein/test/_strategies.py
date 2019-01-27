# Copyright (c) 2017-2018. See LICENSE for details.

"""
Hypothesis strategies.
"""

from csv import reader as csvReader
from os.path import dirname, join
from string import ascii_letters, digits
from sys import maxunicode
from typing import Callable, Iterable, Optional, Sequence, Text, TypeVar

from hyperlink import DecodedURL, EncodedURL

from hypothesis import assume
from hypothesis.strategies import (
    characters, composite, integers, lists, sampled_from, text
)

from idna import IDNAError, check_label, encode as idna_encode

from twisted.python.compat import _PY3, unicode

Iterable, Optional, Sequence, Text  # Silence linter


__all__ = ()


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
def ascii_text(draw, min_size=0, max_size=None):  # pragma: no cover
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
def latin1_text(draw, min_size=0, max_size=None):
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
def idna_text(draw, min_size=0, max_size=None):  # pragma: no cover
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

        try:
            label.encode("ascii")
        except UnicodeEncodeError:
            # If the label doesn't encode to ASCII, then we need to check the
            # length of the label after encoding to punycode and adding the
            # xn-- prefix.
            while len(label.encode("punycode")) > 63 - len("xn--"):
                # Rather than bombing out, just trim from the end until it is
                # short enough, so hypothesis doesn't have to generate new
                # data.
                label = label[:-1]

    else:
        label = draw(text(
            min_size=1, max_size=63,
            alphabet=unicode(ascii_letters + digits + u"-")
        ))

    # Filter invalid labels.
    # It would be better not to generate bogus labels in the first place... but
    # that's not trivial.
    try:
        check_label(label)
    except UnicodeError:
        assume(False)

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
        lists(hostname_labels(allow_idn=allow_idn), min_size=1, max_size=5)
        .filter(lambda ls: sum(len(l) for l in ls) + len(ls) - 1 <= 252)
    )

    name = u".".join(labels)

    # Filter names that are not IDNA-encodable.
    # We try pretty hard not to generate bogus names in the first place... but
    # catching all cases is not trivial.
    try:
        idna_encode(name)
    except IDNAError:
        assume(False)

    return name


def path_characters():
    # type: () -> str
    """
    Returns a string containing valid URL path characters.
    """
    global _path_characters

    if _path_characters is None:
        def chars():
            # type: () -> Iterable[Text]
            for i in range(maxunicode):
                c = unichr(i)

                # Exclude reserved characters
                if c in "#/?":
                    continue

                # Exclude anything not UTF-8 compatible
                try:
                    c.encode("utf-8")
                except UnicodeEncodeError:
                    continue

                yield c

        _path_characters = "".join(chars())

    return _path_characters

_path_characters = None  # type: Optional[str]


@composite
def paths(draw):  # pragma: no cover
    # type: (DrawCallable) -> Sequence[Text]
    return draw(
        lists(text(min_size=1, alphabet=path_characters()), max_size=10)
    )


@composite
def encoded_urls(draw):  # pragma: no cover
    # type: (DrawCallable) -> EncodedURL
    """
    A strategy which generates L{EncodedURL}s.
    Call the L{EncodedURL.to_uri} method on each URL to get an HTTP
    protocol-friendly URI.
    """
    port = draw(port_numbers(allow_zero=True))
    host = draw(hostnames())
    path = draw(paths())

    if port == 0:
        port = None

    args = dict(
        scheme=draw(sampled_from((u"http", u"https"))),
        host=host, port=port, path=path,
    )

    return EncodedURL(**args)


@composite
def decoded_urls(draw):  # pragma: no cover
    # type: (DrawCallable) -> DecodedURL
    """
    A strategy which generates L{DecodedURL}s.
    Call the L{EncodedURL.to_uri} method on each URL to get an HTTP
    protocol-friendly URI.
    """
    return DecodedURL(draw(encoded_urls()))
