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
    convertRawHeaders, convertRawHeadersFrozen, getFromRawHeaders,
    normalizeHeaderName,
    headerNameAsBytes, headerNameAsText, headerValueAsBytes, headerValueAsText,
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



class HeaderNameNormalizationTests(TestCase):
    """
    Tests for header name normalization.
    """

    def test_normalizeLowerCase(self):
        # type: (Text) -> None
        """
        L{normalizeHeaderName} normalizes header names to lower case.
        """
        self.assertEqual(normalizeHeaderName("FooBar"), "foobar")



class RawHeadersConversionTests(TestCase):
    """
    Tests for L{convertRawHeaders}.
    """

    def test_pairNotTuple(self):
        # type: () -> None
        """
        L{convertRawHeaders} raises L{TypeError} if the C{headerPairs}
        argument is not an tuple L{tuple}s.
        """
        e = self.assertRaises(
            TypeError, tuple, convertRawHeaders(([b"k", b"v"],))
        )
        self.assertEqual(str(e), "header pair must be a tuple")


    def test_pairsWrongLength(self):
        # type: () -> None
        """
        L{convertRawHeaders} raises L{ValueError} if the C{headerPairs}
        argument is not an tuple of 2-item L{tuple}s.
        """
        for pair in ((b"k",), (b"k", b"v", b"x")):
            e = self.assertRaises(
                ValueError, tuple, convertRawHeaders((pair,))
            )
            self.assertEqual(str(e), "header pair must be a 2-tuple")


    def test_pairsNameNotBytes(self):
        # type: () -> None
        """
        L{convertRawHeaders} raises L{TypeError} if the C{headerPairs}
        argument is not an tuple of 2-item L{tuple}s where the first item in
        the 2-item L{tuple} is L{bytes}.
        """
        e = self.assertRaises(
            TypeError, tuple, convertRawHeaders(((u"k", b"v"),))
        )
        self.assertEqual(str(e), "header name must be bytes")


    def test_pairsValueNotBytes(self):
        # type: () -> None
        """
        L{convertRawHeaders} raises L{TypeError} if the C{headerPairs}
        argument is not an tuple of 2-item L{tuple}s where the second item
        in the 2-item L{tuple} is bytes.
        """
        e = self.assertRaises(
            TypeError,
            tuple, convertRawHeaders(headerPairs=((b"k", u"v"),))
        )
        self.assertEqual(str(e), "header value must be bytes")



class GetValuesTestsMixIn(object):
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
        rawHeaders = (
            (b"a", b"1"), (b"b", b"2"), (b"c", b"3"), (b"B", b"TWO")
        )

        normalized = defaultdict(list)  # type: Dict[bytes, List[bytes]]
        for name, value in rawHeaders:
            normalized[normalizeHeaderName(name)].append(value)

        for name, values in normalized.items():
            self.assertEqual(
                list(self.getValues(rawHeaders, name)), values,
                "header name: {!r}".format(name)
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
        for name, value in textHeaders:
            textValues[normalizeHeaderName(name)].append(value)

        rawHeaders = tuple(
            (headerNameAsBytes(name), headerValueAsBytes(value))
            for name, value in textHeaders
        )

        for name, _values in textValues.items():
            self.assertEqual(
                list(self.getValues(rawHeaders, name)), _values,
                "header name: {!r}".format(name)
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
            binaryValues[headerNameAsText(normalizeHeaderName(name))].append(
                value
            )

        for textName, values in binaryValues.items():
            self.assertEqual(
                tuple(self.getValues(rawHeaders, textName)),
                tuple(headerValueAsText(value) for value in values),
                "header name: {!r}".format(textName)
            )


    def test_getInvalidNameType(self):
        # type: () -> None
        """
        C{getValues} raises L{TypeError} when the given header name is of an
        unknown type.
        """
        e = self.assertRaises(TypeError, self.getValues, (), object())
        self.assertEqual(str(e), "name must be text or bytes")



class RawHeadersReadTests(GetValuesTestsMixIn, TestCase):
    """
    Tests for utilities that access data from the "headers tartare" internal
    representation.
    """

    @staticmethod
    def getValues(rawHeaders, name):
        return getFromRawHeaders(convertRawHeadersFrozen(rawHeaders), name)



class FrozenHTTPHeadersTests(GetValuesTestsMixIn, TestCase):
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



class MutableHTTPHeadersTests(GetValuesTestsMixIn, TestCase):
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


    def test_removeBytesName(self):
        # type: () -> None
        """
        C{MutableHTTPHeaders.remove} removes all values for the given L{bytes}
        header name.
        """
        rawHeaders = ((b"a", b"1"), (b"b", b"2a"), (b"c", b"3"), (b"b", b"2b"))
        headers = MutableHTTPHeaders(rawHeaders=rawHeaders)
        headers.remove(b"b")

        self.assertEqual(headers.rawHeaders, ((b"a", b"1"), (b"c", b"3")))


    def test_removeTextName(self):
        # type: () -> None
        """
        C{MutableHTTPHeaders.remove} removes all values for the given L{Text}
        header name.
        """
        rawHeaders = ((b"a", b"1"), (b"b", b"2a"), (b"c", b"3"), (b"b", b"2b"))
        headers = MutableHTTPHeaders(rawHeaders=rawHeaders)
        headers.remove(u"b")

        self.assertEqual(headers.rawHeaders, ((b"a", b"1"), (b"c", b"3")))


    def test_removeInvalidNameType(self):
        # type: () -> None
        """
        C{MutableHTTPHeaders.remove} raises L{TypeError} when the given header
        name is of an unknown type.
        """
        headers = MutableHTTPHeaders(rawHeaders=())

        e = self.assertRaises(TypeError, headers.remove, object())
        self.assertEqual(str(e), "name must be text or bytes")


    def test_addValueBytesName(self):
        # type: () -> None
        """
        C{MutableHTTPHeaders.addValue} adds the given L{bytes} value for the
        given L{bytes} header name.
        """
        rawHeaders = ((b"a", b"1"), (b"b", b"2a"))
        headers = MutableHTTPHeaders(rawHeaders=rawHeaders)
        headers.addValue(b"b", b"2b")

        self.assertEqual(
            headers.rawHeaders, ((b"a", b"1"), (b"b", b"2a"), (b"b", b"2b"))
        )


    def test_addValueTextName(self):
        # type: () -> None
        """
        C{MutableHTTPHeaders.addValue} adds the given L{Text} value for the
        given L{Text} header name.
        """
        rawHeaders = ((b"a", b"1"), (b"b", b"2a"))
        headers = MutableHTTPHeaders(rawHeaders=rawHeaders)
        headers.addValue(u"b", u"2b")

        self.assertEqual(
            headers.rawHeaders, ((b"a", b"1"), (b"b", b"2a"), (b"b", b"2b"))
        )


    def test_addValueBytesNameTextValue(self):
        # type: () -> None
        """
        C{MutableHTTPHeaders.addValue} raises L{TypeError} when the given
        header name is L{bytes} and the given value is L{Text}.
        """
        headers = MutableHTTPHeaders(rawHeaders=())

        e = self.assertRaises(TypeError, headers.addValue, b"a", u"1")
        self.assertEqual(str(e), "value must be bytes to match name")


    def test_addValueTextNameBytesValue(self):
        # type: () -> None
        """
        C{MutableHTTPHeaders.addValue} raises L{TypeError} when the given
        header name is L{Text} and the given value is L{bytes}.
        """
        headers = MutableHTTPHeaders(rawHeaders=())

        e = self.assertRaises(TypeError, headers.addValue, u"a", b"1")
        self.assertEqual(str(e), "value must be text to match name")


    def test_addValueInvalidNameType(self):
        # type: () -> None
        """
        C{MutableHTTPHeaders.addValue} raises L{TypeError} when the given
        header name is of an unknown type.
        """
        headers = MutableHTTPHeaders(rawHeaders=())

        e = self.assertRaises(TypeError, headers.addValue, object(), b"1")
        self.assertEqual(str(e), "name must be text or bytes")



class HTTPHeadersFromHeadersTests(GetValuesTestsMixIn, TestCase):
    """
    Tests for L{HTTPHeadersFromHeaders}.
    """

    @staticmethod
    def getValues(rawHeaders, name):
        webHeaders = Headers()
        for rawName, rawValue in rawHeaders:
            webHeaders.addRawHeader(rawName, rawValue)

        headers = HTTPHeadersFromHeaders(headers=webHeaders)

        return headers.getValues(name)


    def test_interface(self):
        # type: () -> None
        """
        L{HTTPHeadersFromHeaders} implements L{IHTTPHeaders}.
        """
        headers = HTTPHeadersFromHeaders(headers=Headers({}))
        self.assertProvides(IHTTPHeaders, headers)


    def test_rawHeaders(self):
        # type: () -> None
        """
        L{MutableHTTPHeaders.rawHeaders} returns raw headers matching the
        L{Headers} given at init time.
        """
        rawHeaders = ((b"b", b"2a"), (b"a", b"1"), (b"B", b"2b"))
        webHeaders = Headers()
        for name, value in rawHeaders:
            webHeaders.addRawHeader(name, value)
        headers = HTTPHeadersFromHeaders(headers=webHeaders)

        # Note that Headers does not give you back header names in network
        # order, but it should give us back values in network order.
        # So we need to normalize our way around.

        normalizedRawHeaders = convertRawHeadersFrozen(rawHeaders)

        self.assertEqual(
            sorted(headers.rawHeaders), sorted(normalizedRawHeaders)
        )
