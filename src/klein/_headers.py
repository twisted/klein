# -*- test-case-name: klein.test.test_request -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
HTTP headers.
"""

from attr import Factory, attrib, attrs
from attr.validators import instance_of, optional, provides

from twisted.python.compat import unicode
from twisted.web.http_headers import Headers

from zope.interface import Attribute, Interface, implementer


__all__ = ()



# Interfaces

class IHTTPHeaders(Interface):
    """
    HTTP entity headers.
    """

    rawHeaders = Attribute(
        """
        Raw header data as a tuple in the from: C{((name, value), ...)}.
        C{name} and C{value} are bytes.
        Headers are provided in the order that they were received.
        Headers with multiple values are provided as separate name and value
        pairs.
        """
    )


    def get(name):
        """
        Get the values associated with the given header name.

        If the given name is L{bytes}, the value will be returned as the
        raw header L{bytes}.

        If the given name is L{unicode}, the value will be returned as
        L{unicode} text, by decoding the raw header bytes as UTF-8 text if
        possible, and
        """



# Simple implementation

def headersTartare(values):
    if type(values) is tuple:
        for pair in values:
            if type(pair) is tuple:
                name, value = pair
                bytes(name), bytes(value)
            else:
                break
        else:
            return values

    return tuple((bytes(name), bytes(value)) for name, value in values)


def headerValueAsUnicode(value):
    """
    Convert a header value (L{bytes}) to text (L{unicode}).
    This tries to decode as UTF-8, and if that fails uses "charmap".
    """
    try:
        return value.decode("utf-8")
    except UnicodeDecodeError:
        return value.decode("charmap")



@implementer(IHTTPHeaders)
@attrs(frozen=True)
class FrozenHTTPHeaders(object):
    """
    HTTP entity headers.
    """

    rawHeaders = attrib(convert=headersTartare)


    def get(self, name):
        if type(name) is bytes:
            return (v for n, v in self.rawHeaders if name == n)

        if type(name) is unicode:
            rawName = name.encode("ascii")
            return(
                headerValueAsUnicode(v)
                for n, v in self.rawHeaders if rawName == n
            )

        raise TypeError("name must be unicode or bytes")



# Support for L{Headers}

@implementer(IHTTPHeaders)
@attrs(frozen=True)
class HTTPHeadersFromHeaders(object):
    """
    HTTP entity headers.

    This is an L{IHTTPHeaders} implementation that wraps a L{Headers} object.

    This is used by Klein to expose objects from L{twisted.web} to clients
    while presenting the Klein interface.
    """

    @attrs(frozen=False)
    class _State(object):
        """
        Internal mutable state for L{HTTPRequestFromIRequest}.
        """

    _headers = attrib(validator=instance_of(Headers))
    _state = attrib(default=Factory(_State), init=False)


    @property
    def rawHeaders(self):
        raise NotImplementedError()
