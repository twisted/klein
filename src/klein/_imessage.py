# Copyright (c) 2017-2018. See LICENSE for details.

"""
Interfaces related to HTTP messages.

Do not import directly from here, except:
 * From _interfaces.py.
 * From implementations of these interfaces, but even then, import the
   zope.interface.Interface classes via _interfaces.py.

This will ensure that type checking works.
"""

from typing import AnyStr, Iterable, MutableSequence, Sequence, Text, Tuple

from hyperlink import DecodedURL

from tubes.itube import IFount

from twisted.internet.defer import Deferred

from zope.interface import Attribute, Interface

from ._typing import ifmethod

AnyStr, DecodedURL, Deferred, Iterable, IFount, Text  # Silence linter


__all__ = ()


RawHeader = Tuple[bytes, bytes]
RawHeaders = Sequence[RawHeader]
MutableRawHeaders = MutableSequence[RawHeader]



class FountAlreadyAccessedError(Exception):
    """
    The HTTP message's fount has already been accessed and is no longer
    available.
    """



class IHTTPHeaders(Interface):
    """
    HTTP entity headers.

    HTTP headers names and values are sort-of-but-not-quite-specifically
    expected to be text.

    Because the specifications are somewhat vague, and implementations vary in
    fidelity, both header names and values must be made available as the
    original bytes received from the network.
    This interface also makes them available as an ordered sequence of name and
    value pairs so that they can be iterated in the same order as they were
    received on the network.

    As such, the C{rawHeaders} attribute provides the header data as a sequence
    of C{(name, value)} L{tuple}s.

    A dictionary-like interface that maps text names to an ordered sequence of
    text values.
    This interface assumes that both header name bytes and header value bytes
    are encoded as ISO-8859-1.

    Note that header name bytes should be strictly encoded as ASCII; this
    interface uses ISO-8859-1 to provide interoperability with (naughty) HTTP
    implementations that send non-ASCII data.
    Because ISO-8859-1 is a superset of ASCII, this will still work for
    well-behaved implementations.
    """

    rawHeaders = Attribute(
        """
        Raw header data as a tuple in the from: C{((name, value), ...)}.
        C{name} and C{value} are bytes.
        Headers are provided in the order that they were received.
        Headers with multiple values are provided as separate name and value
        pairs.
        """
    )  # type: RawHeaders


    @ifmethod
    def getValues(name):
        # type: (AnyStr) -> Iterable[AnyStr]
        """
        Get the values associated with the given header name.

        If the given name is L{bytes}, the value will be returned as the raw
        header L{bytes}.

        If the given name is L{Text}, the name will be encoded as ISO-8859-1
        and the value will be returned as text, by decoding the raw header
        value bytes with ISO-8859-1.

        @param name: The name of the header to look for.

        @return: The values of the header with the given name.
        """



class IMutableHTTPHeaders(IHTTPHeaders):
    """
    Mutable HTTP entity headers.
    """

    @ifmethod
    def remove(name):
        # type: (AnyStr) -> None
        """
        Remove all header name/value pairs for the given header name.

        If the given name is L{Text}, it will be encoded as ISO-8859-1 before
        comparing to the (L{bytes}) header names.

        @param name: The name of the header to remove.
        """


    @ifmethod
    def addValue(name, value):
        # type: (AnyStr, AnyStr) -> None
        """
        Add the given header name/value pair.

        If the given name is L{bytes}, the value must also be L{bytes}.

        If the given name is L{Text}, it will be encoded as ISO-8859-1, and the
        value, which must also be L{Text}, will be encoded as ISO-8859-1.
        """



class IHTTPMessage(Interface):
    """
    HTTP entity.
    """

    headers = Attribute("Entity headers.")  # type: IHTTPHeaders


    @ifmethod
    def bodyAsFount():
        # type: () -> IFount
        """
        The entity body, as a fount.

        @note: The fount may only be accessed once.
            It provides a mechanism for accessing the body as a stream of data,
            potentially as it is read from the network, without having to cache
            the entire body, which may be large.
            Because there is no caching, it is not possible to "start over" by
            accessing the fount a second time.
            Attempting to do so will raise L{FountAlreadyAccessedError}.

        @raise FountAlreadyAccessedError: If the fount has previously been
            accessed.
        """


    @ifmethod
    def bodyAsBytes():
        # type: () -> Deferred[bytes]
        """
        The entity body, as bytes.

        @note: This necessarily reads the entire entity body into memory,
            which may be a problem if the body is large.

        @note: This method caches the body, which means that unlike
            C{self.bodyAsFount}, calling it repeatedly will return the same
            data.

        @note: This method accesses the fount (via C{self.bodyAsFount}), which
            means the fount will not be available afterwards, and that if
            C{self.bodyAsFount} has previously been called directly, this
            method will raise L{FountAlreadyAccessedError}.

        @raise FountAlreadyAccessedError: If the fount has previously been
            accessed.
        """



class IHTTPRequest(IHTTPMessage):
    """
    HTTP request.
    """

    method = Attribute("Request method.")  # type: Text
    uri    = Attribute("Request URI.")     # type: DecodedURL



class IHTTPResponse(IHTTPMessage):
    """
    HTTP response.
    """

    status = Attribute("Response status code.")  # type: int
