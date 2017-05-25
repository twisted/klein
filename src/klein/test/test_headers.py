# -*- test-case-name: klein.test.test_request -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{klein._headers}.
"""

from collections import defaultdict

from hypothesis import assume, given, note
from hypothesis.strategies import characters, binary, iterables, text, tuples

from twisted.web.http_headers import Headers

from ._strategies import ascii_text, latin1_text
from ._trial import TestCase
from .._headers import (
    FrozenHTTPHeaders, HTTPHeadersFromHeaders,
    HEADER_NAME_ENCODING, HEADER_VALUE_ENCODING,
    IFrozenHTTPHeaders,
    headerNameAsBytes, headerNameAsText,
    headerValueAsBytes, headerValueAsText,
)


__all__ = ()



def encodeName(name):
    try:
        return name.encode(HEADER_NAME_ENCODING)
    except UnicodeEncodeError:
        return None


def encodeValue(name):
    try:
        return name.encode(HEADER_VALUE_ENCODING)
    except UnicodeEncodeError:
        return None



class EncodingTests(TestCase):
    """
    Tests for encoding support in L{klein._headers}.
    """

    @given(binary())
    def test_headerNameAsBytesWithBytes(self, name):
        """
        L{headerNameAsBytes} passes through L{bytes}.
        """
        self.assertIdentical(headerNameAsBytes(name), name)


    @given(text(min_size=1))
    def test_headerNameAsBytesWithUnicode(self, name):
        """
        L{headerNameAsBytes} encodes L{unicode} as ISO-8859-1.
        """
        rawName = encodeName(name)
        assume(rawName is not None)
        self.assertEqual(headerNameAsBytes(name), rawName)


    @given(binary())
    def test_headerValueAsBytesWithBytes(self, value):
        """
        L{headerValueAsBytes} passes through L{bytes}.
        """
        self.assertIdentical(headerValueAsBytes(value), value)


    @given(text(min_size=1))
    def test_headerValueAsBytesWithUnicode(self, value):
        """
        L{headerValueAsBytes} encodes L{unicode} as ISO-8859-1.
        """
        rawValue = encodeName(value)
        assume(rawValue is not None)
        self.assertEqual(headerValueAsBytes(value), rawValue)



class FrozenHTTPHeadersTests(TestCase):
    """
    Tests for L{FrozenHTTPHeaders}.
    """

    def test_interface(self):
        """
        L{FrozenHTTPHeaders} implements L{IFrozenHTTPHeaders}.
        """
        headers = FrozenHTTPHeaders(rawHeaders=())
        self.assertProvides(IFrozenHTTPHeaders, headers)


    def test_rawHeadersNotTuple(self):
        """
        L{FrozenHTTPHeaders} raises L{TypeError} if the C{rawHeaders} argument
        is not an iterable.
        """
        self.assertRaises(TypeError, FrozenHTTPHeaders, rawHeaders=None)


    def test_rawHeadersNameNotBytes(self):
        """
        L{FrozenHTTPHeaders} raises L{TypeError} if the C{rawHeaders} argument
        is not an iterable of 2-item L{tuple}s where the first item in the
        2-item L{tuple} is L{bytes}.
        """
        self.assertRaises(
            TypeError, FrozenHTTPHeaders, rawHeaders=((u"k", b"v"),)
        )


    def test_rawHeadersValueNotBytes(self):
        """
        L{FrozenHTTPHeaders} raises L{TypeError} if the C{rawHeaders} argument
        is not an iterable of 2-item L{tuple}s where the second item in the
        2-item L{tuple} is bytes.
        """
        self.assertRaises(
            TypeError, FrozenHTTPHeaders, rawHeaders=((b"k", u"v"),)
        )


    def test_rawHeadersTupleIdentical(self):
        """
        L{FrozenHTTPHeaders} stores the given C{rawHeaders} argument directly
        if it is a L{tuple} of 2-item L{tuple}s of L{bytes}.
        """
        rawHeaders = ((b"a", b"1"), (b"b", b"2"), (b"c", b"3"))
        self.assertIdentical(
            FrozenHTTPHeaders(rawHeaders=rawHeaders).rawHeaders, rawHeaders
        )


    def test_rawHeadersIterableEquals(self):
        """
        L{FrozenHTTPHeaders} stores the given C{rawHeaders} data if it is an
        iterable of 2-item L{tuple}s of L{bytes}.
        """
        rawHeaders = ((b"a", b"1"), (b"b", b"2"), (b"c", b"3"))
        self.assertEqual(
            FrozenHTTPHeaders(rawHeaders=iter(rawHeaders)).rawHeaders,
            rawHeaders
        )


    def test_rawHeadersPairsIterableEquals(self):
        """
        L{FrozenHTTPHeaders} stores the given C{rawHeaders} data if it is a
        L{tuple} of 2-item iterables of L{bytes}.
        """
        rawHeaders = ((b"a", b"1"), (b"b", b"2"), (b"c", b"3"))
        self.assertEqual(
            FrozenHTTPHeaders(
                rawHeaders=tuple(iter(p) for p in rawHeaders)
            ).rawHeaders,
            rawHeaders
        )


    def test_rawHeadersTuplePairsWrongLength(self):
        """
        L{FrozenHTTPHeaders} raises L{ValueError} if the given C{rawHeaders}
        data if it is a L{tuple} of iterables of the wrong size.
        """
        self.assertRaises(ValueError, FrozenHTTPHeaders, rawHeaders=((b"k",),))


    def test_rawHeadersIterablePairsWrongLength(self):
        """
        L{FrozenHTTPHeaders} raises L{ValueError} if the given C{rawHeaders}
        data is an iterable of iterables of the wrong size.
        """
        self.assertRaises(
            ValueError, FrozenHTTPHeaders, rawHeaders=iter((b"k",),)
        )


    def test_getBytesName(self):
        """
        L{FrozenHTTPHeaders.get} returns an iterable of L{bytes} values for the
        given L{bytes} header name.
        """
        rawHeaders = ((b"a", b"1"), (b"b", b"2"), (b"c", b"3"))
        headers = FrozenHTTPHeaders(rawHeaders=rawHeaders)

        for name, value in rawHeaders:
            self.assertEqual(tuple(headers.get(name)), (value,))


    @given(iterables(tuples(ascii_text(min_size=1), latin1_text())))
    def test_getUnicodeName(self, textPairs):
        """
        L{FrozenHTTPHeaders.get} returns an iterable of L{unicode} values for
        the given L{unicode} header name.
        """
        note("text pairs: {!r}".format(textPairs))

        textHeaders = tuple((name, value) for name, value in textPairs)

        textValues = defaultdict(list)
        for name, values in textHeaders:
            textValues[name].append(values)

        headers = FrozenHTTPHeaders(rawHeaders=(
            (headerNameAsBytes(name), headerValueAsBytes(value))
            for name, value in textHeaders
        ))
        note("raw headers: {!r}".format(headers.rawHeaders))

        for name, values in textValues.items():
            note("text name: {!r}".format(name))
            note("text values: {!r}".format(values))
            self.assertEqual(list(headers.get(name)), values)


    @given(iterables(tuples(ascii_text(min_size=1), binary())))
    def test_getUnicodeNameBytesValues(self, pairs):
        """
        L{FrozenHTTPHeaders.get} returns an iterable of L{unicode} values for
        the given L{unicode} header name.
        """
        rawHeaders = tuple(
            (headerNameAsBytes(name), value) for name, value in pairs
        )

        binaryValues = defaultdict(list)
        for name, value in rawHeaders:
            binaryValues[headerNameAsText(name)].append(value)

        headers = FrozenHTTPHeaders(rawHeaders=rawHeaders)
        note("raw headers: {!r}".format(headers.rawHeaders))

        for name, values in binaryValues.items():
            note("text name: {!r}".format(name))
            note("binary values: {!r}".format(values))
            self.assertEqual(
                tuple(headers.get(name)),
                tuple(headerValueAsText(v) for v in values)
            )


    def test_getInvalidNameType(self):
        """
        L{FrozenHTTPHeaders.get} raises L{} when the given header name is of an
        unknown type.
        """
        headers = FrozenHTTPHeaders(())
        self.assertRaises(TypeError, headers.get, object())



class HTTPHeadersFromHeadersTests(TestCase):
    """
    Tests for L{HTTPHeadersFromHeaders}.
    """

    def test_interface(self):
        """
        L{HTTPHeadersFromHeaders} implements L{IFrozenHTTPHeaders}.
        """
        headers = HTTPHeadersFromHeaders(Headers({}))
        self.assertProvides(IFrozenHTTPHeaders, headers)

    test_interface.todo = "unimplemented"
