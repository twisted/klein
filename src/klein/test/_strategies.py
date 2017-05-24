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



def is_idna_compatible(label, max_length):
    try:
        idna = label.encode("idna")
    except ValueError:
        return False

    return len(idna) <= max_length


@composite
def port_numbers(draw, allow_zero):
    if allow_zero:
        min_value = 0
    else:
        min_value = 1

    return draw(integers(min_value=min_value, max_value=65535))


@composite
def hostname_labels(draw, allow_idn=True):
    alphabet = unicode(ascii_letters + digits + u"-")
    if allow_idn:
        # FIXME: get a more complete character set
        # Throw in some non-ASCII values for now
        alphabet += u"\N{LATIN SMALL LETTER A WITH ACUTE}"
        alphabet += u"\N{SNOWMAN}"

    label = draw(text(min_size=1, max_size=63, alphabet=alphabet))

    if allow_idn:
        assume(is_idna_compatible(label, 63))

    return label


@composite
def hostnames(draw, allow_leading_digit=True, allow_idn=True):
    labels = draw(lists(hostname_labels(allow_idn=allow_idn), min_size=1))

    name = u".".join(labels)

    if allow_idn:
        assume(is_idna_compatible(name, 252))
    else:
        assume(len(name) <= 252)

    return name


@composite
def http_urls(draw):
    host = draw(hostnames())

    port = draw(port_numbers(allow_zero=True))
    if port == 0:
        port = None

    path = tuple(draw(iterables(text(min_size=1))))

    return URL(
        scheme=draw(sampled_from((u"http", u"https"))),
        host=host, port=port, path=path,
    )
