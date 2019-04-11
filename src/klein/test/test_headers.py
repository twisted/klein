# -*- test-case-name: klein.test.test_headers -*-
# Copyright (c) 2017-2018. See LICENSE for details.

"""
Tests for L{klein._headers}.
"""

from collections import defaultdict
from typing import AnyStr, Dict, Iterable, List, Optional, Text, Tuple, cast

from hypothesis import given
from hypothesis.strategies import binary, iterables, text, tuples

from ._strategies import ascii_text, latin1_text
from ._trial import TestCase
from .._headers import (
    FrozenHTTPHeaders,
    HEADER_NAME_ENCODING, HEADER_VALUE_ENCODING,
    IHTTPHeaders, IMutableHTTPHeaders,
    MutableHTTPHeaders,
    RawHeaders, getFromRawHeaders,
    headerNameAsBytes, headerNameAsText, headerValueAsBytes, headerValueAsText,
    normalizeHeaderName, normalizeRawHeaders, normalizeRawHeadersFrozen,
)

# Silence linter
AnyStr, Dict, Iterable, List, Optional, RawHeaders, Text, Tuple


__all__ = ()



def encodeName(name):
    # type: (Text) -> Optional[bytes]
    return name.encode(HEADER_NAME_ENCODING)


def encodeValue(name):
    # type: (Text) -> Optional[bytes]
    return name.encode(HEADER_VALUE_ENCODING)


def decodeName(name):
    # type: (bytes) -> Text
    return name.decode(HEADER_NAME_ENCODING)


def decodeValue(name):
    # type: (bytes) -> Text
    return name.decode(HEADER_VALUE_ENCODING)


def headerValueSanitize(value):
    # type: (AnyStr) -> AnyStr
    """
    Sanitize a header value by replacing linear whitespace with spaces.
    """
    if isinstance(value, bytes):
        lws = [b'\r\n', b'\r', b'\n']
        space = b' '
    else:
        lws = ['\r\n', '\r', '\n']
        space = ' '
    for l in lws:
        value = value.replace(l, space)
    return value


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


    @given(latin1_text(min_size=1))
    def test_headerNameAsBytesWithText(self, name):
        # type: (Text) -> None
        """
        L{headerNameAsBytes} encodes L{Text} using L{HEADER_NAME_ENCODING}.
        """
        rawName = encodeName(name)
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


    @given(latin1_text(min_size=1))
    def test_headerValueAsBytesWithText(self, value):
        # type: (Text) -> None
        """
        L{headerValueAsBytes} encodes L{Text} using L{HEADER_VALUE_ENCODING}.
        """
        rawValue = encodeValue(value)
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
        # type: () -> None
        """
        L{normalizeHeaderName} normalizes header names to lower case.
        """
        self.assertEqual(normalizeHeaderName("FooBar"), "foobar")



class RawHeadersConversionTests(TestCase):
    """
    Tests for L{normalizeRawHeaders}.
    """

    def test_pairWrongLength(self):
        # type: () -> None
        """
        L{normalizeRawHeaders} raises L{ValueError} if the C{headerPairs}
        argument is not an iterable of 2-item iterables.
        """
        for invalidPair in ((b"k",), (b"k", b"v", b"x")):
            e = self.assertRaises(
                ValueError,
                tuple,
                normalizeRawHeaders(
                    cast(Iterable[Iterable[bytes]], (invalidPair,))
                ),
            )
            self.assertEqual(str(e), "header pair must be a 2-item iterable")


    @given(latin1_text())
    def test_pairNameText(self, name):
        # type: (Text) -> None
        """
        L{normalizeRawHeaders} converts ISO-8859-1-encodable text names into
        bytes.
        """
        rawHeaders = ((name, b"value"),)
        normalized = tuple(normalizeRawHeaders(rawHeaders))

        self.assertEqual(
            normalized,
            ((normalizeHeaderName(headerNameAsBytes(name)), b"value"),),
        )


    @given(latin1_text())
    def test_pairValueText(self, value):
        # type: (Text) -> None
        """
        L{normalizeRawHeaders} converts ISO-8859-1-encodable text values into
        bytes.
        """
        rawHeaders = ((b"name", value),)
        normalized = tuple(normalizeRawHeaders(rawHeaders))

        self.assertEqual(normalized, ((b"name", headerValueAsBytes(value)),))



class GetValuesTestsMixIn(object):
    """
    Tests for utilities that access data from the C{RawHeaders} internal
    representation.
    """

    def getValues(self, rawHeaders, name):
        # type: (RawHeaders, AnyStr) -> Iterable[AnyStr]
        """
        Look up the values for the given header name from the given raw
        headers.

        This is called by the other tests in this mix-in class to allow test
        cases that use it to specify how to perform this look-up in the
        implementation being tested.
        """
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
            cast(TestCase, self).assertEqual(
                list(self.getValues(rawHeaders, name)), values,
                "header name: {!r}".format(name)
            )


    def headerNormalize(self, value):
        # type: (Text) -> Text
        """
        Test hook for the normalization of header text values, which is a
        behavior Twisted has changed after version 18.9.0.
        """
        return value


    @given(iterables(tuples(ascii_text(min_size=1), latin1_text())))
    def test_getTextName(self, textPairs):
        # type: (Iterable[Tuple[Text, Text]]) -> None
        """
        C{getValues} returns an iterable of L{Text} values for
        the given L{Text} header name.

        This test only inserts Latin1 text into the header values, which is
        valid data.
        """
        textHeaders = tuple((name, headerValueSanitize(value))
                            for name, value in textPairs)

        textValues = defaultdict(list)  # type: Dict[Text, List[Text]]
        for name, value in textHeaders:
            textValues[normalizeHeaderName(name)].append(value)

        rawHeaders = tuple(
            (headerNameAsBytes(name), headerValueAsBytes(value))
            for name, value in textHeaders
        )

        for name, _values in textValues.items():
            cast(TestCase, self).assertEqual(
                list(self.getValues(rawHeaders, name)),
                [self.headerNormalize(value) for value in _values],
                "header name: {!r}".format(name)
            )


    @given(iterables(tuples(ascii_text(min_size=1), binary())))
    def test_getTextNameBinaryValues(self, pairs):
        # type: (Iterable[Tuple[Text, bytes]]) -> None
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
            (headerNameAsBytes(name), headerValueSanitize(value))
            for name, value in pairs
        )

        binaryValues = defaultdict(list)  # type: Dict[Text, List[bytes]]
        for name, value in rawHeaders:
            binaryValues[headerNameAsText(normalizeHeaderName(name))].append(
                value
            )

        for textName, values in binaryValues.items():
            cast(TestCase, self).assertEqual(
                tuple(self.getValues(rawHeaders, textName)),
                tuple(self.headerNormalize(headerValueAsText(value))
                      for value in values),
                "header name: {!r}".format(textName)
            )


    def test_getInvalidNameType(self):
        # type: () -> None
        """
        C{getValues} raises L{TypeError} when the given header name is of an
        unknown type.
        """
        e = cast(TestCase, self).assertRaises(
            TypeError, self.getValues, (), object()
        )
        cast(TestCase, self).assertRegex(
            str(e), "name <object object at 0x[0-9a-f]+> must be text or bytes"
        )



class RawHeadersReadTests(GetValuesTestsMixIn, TestCase):
    """
    Tests for utilities that access data from the "headers tartare" internal
    representation.
    """

    def getValues(self, rawHeaders, name):
        # type: (RawHeaders, AnyStr) -> Iterable[AnyStr]
        return getFromRawHeaders(normalizeRawHeadersFrozen(rawHeaders), name)



class FrozenHTTPHeadersTests(GetValuesTestsMixIn, TestCase):
    """
    Tests for L{FrozenHTTPHeaders}.
    """

    def getValues(self, rawHeaders, name):
        # type: (RawHeaders, AnyStr) -> Iterable[AnyStr]
        headers = FrozenHTTPHeaders(rawHeaders=rawHeaders)
        return headers.getValues(name=name)


    def test_interface(self):
        # type: () -> None
        """
        L{FrozenHTTPHeaders} implements L{IHTTPHeaders}.
        """
        headers = FrozenHTTPHeaders(rawHeaders=())
        self.assertProvides(IHTTPHeaders, headers)


    def test_defaultHeaders(self):
        # type: () -> None
        """
        L{FrozenHTTPHeaders.rawHeaders} is empty by default.
        """
        headers = FrozenHTTPHeaders()
        self.assertEqual(headers.rawHeaders, ())



class MutableHTTPHeadersTestsMixIn(GetValuesTestsMixIn):
    """
    Tests for L{IMutableHTTPHeaders} implementations.
    """

    def assertRawHeadersEqual(self, rawHeaders1, rawHeaders2):
        # type: (RawHeaders, RawHeaders) -> None
        cast(TestCase, self).assertEqual(rawHeaders1, rawHeaders2)


    def headers(self, rawHeaders):
        # type: (RawHeaders) -> IMutableHTTPHeaders
        raise NotImplementedError(
            "{} must implement headers()".format(self.__class__)
        )


    def getValues(self, rawHeaders, name):
        # type: (RawHeaders, AnyStr) -> Iterable[AnyStr]
        headers = self.headers(rawHeaders=rawHeaders)
        return headers.getValues(name=name)


    def test_interface(self):
        # type: () -> None
        """
        Class implements L{IMutableHTTPHeaders}.
        """
        headers = self.headers(rawHeaders=())
        cast(TestCase, self).assertProvides(IMutableHTTPHeaders, headers)


    def test_rawHeaders(self):
        # type: () -> None
        """
        L{IMutableHTTPHeaders.rawHeaders} equals the raw headers passed at init
        time as a tuple.
        """
        rawHeaders = [(b"a", b"1"), (b"b", b"2"), (b"c", b"3")]
        headers = self.headers(rawHeaders=rawHeaders)
        self.assertRawHeadersEqual(headers.rawHeaders, tuple(rawHeaders))


    def test_removeBytesName(self):
        # type: () -> None
        """
        L{IMutableHTTPHeaders.remove} removes all values for the given L{bytes}
        header name.
        """
        rawHeaders = ((b"a", b"1"), (b"b", b"2a"), (b"c", b"3"), (b"b", b"2b"))
        headers = self.headers(rawHeaders=rawHeaders)
        headers.remove(name=b"b")

        self.assertRawHeadersEqual(
            headers.rawHeaders, ((b"a", b"1"), (b"c", b"3"))
        )


    def test_removeTextName(self):
        # type: () -> None
        """
        L{IMutableHTTPHeaders.remove} removes all values for the given L{Text}
        header name.
        """
        rawHeaders = ((b"a", b"1"), (b"b", b"2a"), (b"c", b"3"), (b"b", b"2b"))
        headers = self.headers(rawHeaders=rawHeaders)
        headers.remove(name=u"b")

        self.assertRawHeadersEqual(
            headers.rawHeaders, ((b"a", b"1"), (b"c", b"3"))
        )


    def test_removeInvalidNameType(self):
        # type: () -> None
        """
        L{IMutableHTTPHeaders.remove} raises L{TypeError} when the given header
        name is of an unknown type.
        """
        headers = self.headers(rawHeaders=())

        e = cast(TestCase, self).assertRaises(
            TypeError, headers.remove, object()
        )
        cast(TestCase, self).assertRegex(
            str(e), "name <object object at 0x[0-9a-f]+> must be text or bytes"
        )


    def test_addValueBytesName(self):
        # type: () -> None
        """
        L{IMutableHTTPHeaders.addValue} adds the given L{bytes} value for the
        given L{bytes} header name.
        """
        rawHeaders = ((b"a", b"1"), (b"b", b"2a"))
        headers = self.headers(rawHeaders=rawHeaders)
        headers.addValue(name=b"b", value=b"2b")

        self.assertRawHeadersEqual(
            headers.rawHeaders, ((b"a", b"1"), (b"b", b"2a"), (b"b", b"2b"))
        )


    def test_addValueTextName(self):
        # type: () -> None
        """
        L{IMutableHTTPHeaders.addValue} adds the given L{Text} value for the
        given L{Text} header name.
        """
        rawHeaders = ((b"a", b"1"), (b"b", b"2a"))
        headers = self.headers(rawHeaders=rawHeaders)
        headers.addValue(name=u"b", value=u"2b")

        self.assertRawHeadersEqual(
            headers.rawHeaders, ((b"a", b"1"), (b"b", b"2a"), (b"b", b"2b"))
        )


    def test_addValueBytesNameTextValue(self):
        # type: () -> None
        """
        L{IMutableHTTPHeaders.addValue} raises L{TypeError} when the given
        header name is L{bytes} and the given value is L{Text}.
        """
        headers = self.headers(rawHeaders=())

        e = cast(TestCase, self).assertRaises(
            TypeError, headers.addValue, b"a", u"1"
        )
        cast(TestCase, self).assertRegex(
            str(e), "value u?'1' must be bytes to match name b?'a'"
        )


    def test_addValueTextNameBytesValue(self):
        # type: () -> None
        """
        L{IMutableHTTPHeaders.addValue} raises L{TypeError} when the given
        header name is L{Text} and the given value is L{bytes}.
        """
        headers = self.headers(rawHeaders=())

        e = cast(TestCase, self).assertRaises(
            TypeError, headers.addValue, u"a", b"1"
        )
        cast(TestCase, self).assertRegex(
            str(e), "value b?'1' must be text to match name u?'a'"
        )


    def test_addValueInvalidNameType(self):
        # type: () -> None
        """
        L{IMutableHTTPHeaders.addValue} raises L{TypeError} when the given
        header name is of an unknown type.
        """
        headers = self.headers(rawHeaders=())

        e = cast(TestCase, self).assertRaises(
            TypeError, headers.addValue, object(), b"1"
        )
        cast(TestCase, self).assertRegex(
            str(e), "name <object object at 0x[0-9a-f]+> must be text or bytes"
        )



class MutableHTTPHeadersTests(MutableHTTPHeadersTestsMixIn, TestCase):
    """
    Tests for L{MutableHTTPHeaders}.
    """

    def headers(self, rawHeaders):
        # type: (RawHeaders) -> IMutableHTTPHeaders
        return MutableHTTPHeaders(rawHeaders=rawHeaders)


    def test_defaultHeaders(self):
        # type: () -> None
        """
        L{MutableHTTPHeaders.rawHeaders} is empty by default.
        """
        headers = MutableHTTPHeaders()
        self.assertEqual(headers.rawHeaders, ())
