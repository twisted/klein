# -*- test-case-name: klein.test.test_request -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{klein._headers}.
"""

from collections import defaultdict
from typing import Dict, List, Optional, Text, Tuple

from hypothesis import assume, given
from hypothesis.strategies import binary, iterables, text, tuples

from twisted.web.http_headers import Headers

from ._strategies import ascii_text, latin1_text
from ._trial import TestCase
from .._headers import (
    FrozenHTTPHeaders, HTTPHeadersFromHeaders,
    HEADER_NAME_ENCODING, HEADER_VALUE_ENCODING,
    IHTTPHeaders, IMutableHTTPHeaders,
    MutableHTTPHeaders,
    getFromRawHeaders,
    headerNameAsBytes, headerNameAsText,
    headerValueAsBytes, headerValueAsText,
    validateRawHeaders,
)

Dict, List, Optional, Text, Tuple  # Silence linter


__all__ = ()



def encodeName(name):
    # type: (Text) -> Optional[bytes]
    try:
        return name.encode(HEADER_NAME_ENCODING)
    except UnicodeEncodeError:
        return None


def decodeName(name):
    # type: (bytes) -> Text
    return name.decode(HEADER_NAME_ENCODING)


def encodeValue(name):
    # type: (Text) -> Optional[bytes]
    try:
        return name.encode(HEADER_VALUE_ENCODING)
    except UnicodeEncodeError:
        return None


def decodeValue(name):
    # type: (bytes) -> Text
    return name.decode(HEADER_VALUE_ENCODING)



class EncodingTests(TestCase):
    """
    Tests for encoding support in L{klein._headers}.
    """

    @given(binary())
    def test_headerNameAsBytesWithBytes(self, name):
        # type: (bytes) -> None
        """
        L{headerNameAsBytes} passes through L{bytes}.
        """
        self.assertIdentical(headerNameAsBytes(name), name)


    @given(text(min_size=1))
    def test_headerNameAsBytesWithText(self, name):
        # type: (Text) -> None
        """
        L{headerNameAsBytes} encodes L{Text} using L{HEADER_NAME_ENCODING}.
        """
        rawName = encodeName(name)
        assume(rawName is not None)
        self.assertEqual(headerNameAsBytes(name), rawName)


    @given(binary())
    def test_headerNameAsTextWithBytes(self, name):
        # type: (bytes) -> None
        """
        L{headerNameAsText} decodes L{bytes} using L{HEADER_NAME_ENCODING}.
        """
        self.assertEqual(headerNameAsText(name), decodeName(name))


    @given(text(min_size=1))
    def test_headerNameAsTextWithText(self, name):
        # type: (Text) -> None
        """
        L{headerNameAsText} passes through L{Text}.
        """
        self.assertIdentical(headerNameAsText(name), name)


    @given(binary())
    def test_headerValueAsBytesWithBytes(self, value):
        # type: (bytes) -> None
        """
        L{headerValueAsBytes} passes through L{bytes}.
        """
        self.assertIdentical(headerValueAsBytes(value), value)


    @given(text(min_size=1))
    def test_headerValueAsBytesWithText(self, value):
        # type: (Text) -> None
        """
        L{headerValueAsBytes} encodes L{Text} using L{HEADER_VALUE_ENCODING}.
        """
        rawValue = encodeName(value)
        assume(rawValue is not None)
        self.assertEqual(headerValueAsBytes(value), rawValue)


    @given(binary())
    def test_headerValueAsTextWithBytes(self, value):
        # type: (bytes) -> None
        """
        L{headerValueAsText} decodes L{bytes} using L{HEADER_VALUE_ENCODING}.
        """
        self.assertEqual(headerValueAsText(value), decodeValue(value))


    @given(text(min_size=1))
    def test_headerValueAsTextWithText(self, value):
        # type: (Text) -> None
        """
        L{headerValueAsText} passes through L{Text}.
        """
        self.assertIdentical(headerValueAsText(value), value)



class RawHeadersValidationTests(TestCase):
    """
    Tests for L{validateRawHeaders}.
    """

    def test_pairNotTuple(self):
        # type: () -> None
        """
        L{validateRawHeaders} raises L{TypeError} if the C{headerPairs}
        argument is not an tuple L{tuple}s.
        """
        e = self.assertRaises(
            TypeError, validateRawHeaders, None, None, ([b"k", b"v"],)
        )
        self.assertEqual(str(e), "header pair must be a tuple")


    def test_pairsWrongLength(self):
        # type: () -> None
        """
        L{validateRawHeaders} raises L{ValueError} if the C{headerPairs}
        argument is not an tuple of 2-item L{tuple}s.
        """
        for pair in ((b"k",), (b"k", b"v", b"x")):
            e = self.assertRaises(
                ValueError, validateRawHeaders, None, None, (pair,)
            )
            self.assertEqual(str(e), "header pair must be a 2-tuple")


    def test_pairsNameNotBytes(self):
        # type: () -> None
        """
        L{validateRawHeaders} raises L{TypeError} if the C{headerPairs}
        argument is not an tuple of 2-item L{tuple}s where the first item in
        the 2-item L{tuple} is L{bytes}.
        """
        e = self.assertRaises(
            TypeError, validateRawHeaders, None, None, ((u"k", b"v"),)
        )
        self.assertEqual(str(e), "header name must be bytes")


    def test_pairsValueNotBytes(self):
        # type: () -> None
        """
        L{validateRawHeaders} raises L{TypeError} if the C{headerPairs}
        argument is not an tuple of 2-item L{tuple}s where the second item
        in the 2-item L{tuple} is bytes.
        """
        e = self.assertRaises(
            TypeError,
            validateRawHeaders, None, None, headerPairs=((b"k", u"v"),)
        )
        self.assertEqual(str(e), "header value must be bytes")



class GetValuestestsMixIn(object):
    """
    Tests for utilities that access data from the "headers tartare" internal
    representation.
    """

    def getValues(self, rawHeaders, name):
        raise NotImplementedError(
            "{} must implement getValues()".format(self.__class__)
        )


    def test_getBytesName(self):
        # type: () -> None
        """
        C{getValues} returns an iterable of L{bytes} values for the
        given L{bytes} header name.
        """
        rawHeaders = ((b"a", b"1"), (b"b", b"2"), (b"c", b"3"))

        for name, value in rawHeaders:
            self.assertEqual(
                tuple(self.getValues(rawHeaders, name)), (value,)
            )


    @given(iterables(tuples(ascii_text(min_size=1), latin1_text())))
    def test_getTextName(self, textPairs):
        # type: (Tuple[Text, Text]) -> None
        """
        C{getValues} returns an iterable of L{Text} values for
        the given L{Text} header name.

        This test only inserts Latin1 text into the header values, which is
        valid data.
        """
        textHeaders = tuple((name, value) for name, value in textPairs)

        textValues = defaultdict(list)  # type: Dict[Text, List[Text]]
        for name, values in textHeaders:
            textValues[name].append(values)

        rawHeaders = tuple(
            (headerNameAsBytes(name), headerValueAsBytes(value))
            for name, value in textHeaders
        )

        for name, _values in textValues.items():
            self.assertEqual(
                list(self.getValues(rawHeaders, name)), _values
            )


    @given(iterables(tuples(ascii_text(min_size=1), binary())))
    def test_getTextNameBinaryValues(self, pairs):
        # type: (Tuple[Text, bytes]) -> None
        """
        C{getValues} returns an iterable of L{Text} values for
        the given L{Text} header name.

        This test only inserts binary data into the header values, which
        includes invalid data if you are a sane person, but arguably
        technically valid if you read the spec because the spec is unclear
        about header encodings, so we made sure that works also, if only sort
        of.
        """
        rawHeaders = tuple(
            (headerNameAsBytes(name), value) for name, value in pairs
        )

        binaryValues = defaultdict(list)  # type: Dict[Text, List[bytes]]
        for name, value in rawHeaders:
            binaryValues[headerNameAsText(name)].append(value)

        for textName, values in binaryValues.items():
            self.assertEqual(
                tuple(self.getValues(rawHeaders, textName)),
                tuple(headerValueAsText(value) for value in values)
            )


    def test_getInvalidNameType(self):
        # type: () -> None
        """
        C{getValues} raises L{} when the given header name is of an
        unknown type.
        """
        e = self.assertRaises(TypeError, self.getValues, (), object())
        self.assertEqual(str(e), "name must be text or bytes")



class RawHeadersReadTests(GetValuestestsMixIn, TestCase):
    """
    Tests for utilities that access data from the "headers tartare" internal
    representation.
    """

    @staticmethod
    def getValues(rawHeaders, name):
        return getFromRawHeaders(rawHeaders, name)



class FrozenHTTPHeadersTests(GetValuestestsMixIn, TestCase):
    """
    Tests for L{FrozenHTTPHeaders}.
    """

    @staticmethod
    def getValues(rawHeaders, name):
        headers = FrozenHTTPHeaders(rawHeaders=rawHeaders)
        return headers.getValues(name)


    def test_interface(self):
        # type: () -> None
        """
        L{FrozenHTTPHeaders} implements L{IHTTPHeaders}.
        """
        headers = FrozenHTTPHeaders(rawHeaders=())
        self.assertProvides(IHTTPHeaders, headers)



class MutableHTTPHeadersTests(GetValuestestsMixIn, TestCase):
    """
    Tests for L{MutableHTTPHeaders}.
    """

    @staticmethod
    def getValues(rawHeaders, name):
        headers = MutableHTTPHeaders(rawHeaders=rawHeaders)
        return headers.getValues(name)


    def test_interface(self):
        # type: () -> None
        """
        L{MutableHTTPHeaders} implements L{IMutableHTTPHeaders}.
        """
        headers = MutableHTTPHeaders(rawHeaders=())
        self.assertProvides(IMutableHTTPHeaders, headers)


    def test_rawHeaders(self):
        # type: () -> None
        """
        L{MutableHTTPHeaders.rawHeaders} returns the raw headers passed at init
        time as a tuple.
        """
        rawHeaders = [(b"a", b"1"), (b"b", b"2"), (b"c", b"3")]
        headers = MutableHTTPHeaders(rawHeaders=rawHeaders)
        self.assertEqual(headers.rawHeaders, tuple(rawHeaders))



class HTTPHeadersFromHeadersTests(TestCase):
    """
    Tests for L{HTTPHeadersFromHeaders}.
    """

    def test_interface(self):
        # type: () -> None
        """
        L{HTTPHeadersFromHeaders} implements L{IHTTPHeaders}.
        """
        headers = HTTPHeadersFromHeaders(headers=Headers({}))
        self.assertProvides(IHTTPHeaders, headers)

    test_interface.todo = "unimplemented"
