# -*- test-case-name: klein.test.test_request -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Hypothesis strategies.
"""

from string import ascii_letters, digits, punctuation

from hyperlink import URL

from hypothesis import assume
from hypothesis.strategies import (
    composite, lists, integers, iterables, sampled_from, text
)


__all__ = ()



def _is_idna_compatible(text, max_length):
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
    """
    A strategy which generates host name labels.

    @param allow_idn: Whether to allow non-ASCII characters as allowed by
        internationalized domain names (IDNs).
    """
    alphabet = unicode(ascii_letters + digits + u"-")
    if allow_idn:
        # FIXME: get a more complete character set
        # Throw in some non-ASCII values for now
        alphabet += u"\N{LATIN SMALL LETTER A WITH ACUTE}"
        alphabet += u"\N{SNOWMAN}"

    label = draw(text(min_size=1, max_size=63, alphabet=alphabet))

    if allow_idn:
        assume(_is_idna_compatible(label, 63))

    return label


@composite
def hostnames(draw, allow_leading_digit=True, allow_idn=True):
    """
    A strategy which generates host names.

    @param allow_leading_digit: Whether to allow a leading digit in host names;
        they were not allowed prior to RFC 1123.

    @param allow_idn: Whether to allow non-ASCII characters as allowed by
        internationalized domain names (IDNs).
    """
    labels = draw(lists(hostname_labels(allow_idn=allow_idn), min_size=1))

    name = u".".join(labels)

    if allow_idn:
        assume(_is_idna_compatible(name, 252))
    else:
        assume(len(name) <= 252)

    return name


@composite
def http_urls(draw):
    """
    A strategy which generates (human-friendly, unicode) IRI-form L{URL}s.
    Call the C{asURI} method on each URL to get a (network-friendly, ASCII)
    URI.
    """
    host = draw(hostnames())

    port = draw(port_numbers(allow_zero=True))
    if port == 0:
        port = None

    path = tuple(draw(iterables(text(min_size=1))))

    return URL(
        scheme=draw(sampled_from((u"http", u"https"))),
        host=host, port=port, path=path,
    )
