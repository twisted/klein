# -*- test-case-name: klein.test.test_headers -*-
# Copyright (c) 2011-2021. See LICENSE for details.

"""
Tests for L{klein._headers}.
"""

from abc import ABC, abstractmethod
from collections import defaultdict
from string import ascii_letters
from typing import (
    AnyStr,
    Callable,
    Dict,
    Iterable,
    List,
    Optional,
    Tuple,
    TypeVar,
    cast,
)

from hypothesis import given
from hypothesis.strategies import (
    binary,
    characters,
    composite,
    iterables,
    lists,
    text,
    tuples,
)

from .._headers import (
    HEADER_NAME_ENCODING,
    HEADER_VALUE_ENCODING,
    FrozenHTTPHeaders,
    IHTTPHeaders,
    IMutableHTTPHeaders,
    MutableHTTPHeaders,
    RawHeaders,
    getFromRawHeaders,
    headerNameAsBytes,
    headerNameAsText,
    headerValueAsBytes,
    headerValueAsText,
    normalizeHeaderName,
    normalizeRawHeaders,
    normalizeRawHeadersFrozen,
)
from ._trial import TestCase


__all__ = ()


T = TypeVar("T")
DrawCallable = Callable[[Callable[..., T]], T]


@composite
def ascii_text(
    draw: DrawCallable,
    min_size: Optional[int] = 0,
    max_size: Optional[int] = None,
) -> str:  # pragma: no cover
    """
    A strategy which generates ASCII-encodable text.

    @param min_size: The minimum number of characters in the text.
        C{None} is treated as C{0}.

    @param max_size: The maximum number of characters in the text.
        Use C{None} for an unbounded size.
    """
    return cast(
        str,
        draw(
            text(min_size=min_size, max_size=max_size, alphabet=ascii_letters)
        ),
    )


@composite  # pragma: no cover
def latin1_text(
    draw: DrawCallable,
    min_size: Optional[int] = 0,
    max_size: Optional[int] = None,
) -> str:
    """
    A strategy which generates ISO-8859-1-encodable text.

    @param min_size: The minimum number of characters in the text.
        C{None} is treated as C{0}.

    @param max_size: The maximum number of characters in the text.
        Use C{None} for an unbounded size.
    """
    return "".join(
        draw(
            lists(
                characters(max_codepoint=255),
                min_size=min_size,
                max_size=max_size,
            )
        )
    )


def encodeName(name: str) -> Optional[bytes]:
    return name.encode(HEADER_NAME_ENCODING)


def encodeValue(name: str) -> Optional[bytes]:
    return name.encode(HEADER_VALUE_ENCODING)


def decodeName(name: bytes) -> str:
    return name.decode(HEADER_NAME_ENCODING)


def decodeValue(name: bytes) -> str:
    return name.decode(HEADER_VALUE_ENCODING)


def headerValueSanitize(value: AnyStr) -> AnyStr:
    """
    Sanitize a header value by replacing linear whitespace with spaces.
    """
    if isinstance(value, bytes):
        lws = [b"\r\n", b"\r", b"\n"]
        space = b" "
    else:
        lws = ["\r\n", "\r", "\n"]
        space = " "
    for lw in lws:
        value = value.replace(lw, space)
    return value


class EncodingTests(TestCase):
    """
    Tests for encoding support in L{klein._headers}.
    """

    @given(binary())
    def test_headerNameAsBytesWithBytes(self, name: bytes) -> None:
        """
        L{headerNameAsBytes} passes through L{bytes}.
        """
        self.assertIdentical(headerNameAsBytes(name), name)

    @given(latin1_text(min_size=1))
    def test_headerNameAsBytesWithText(self, name: str) -> None:
        """
        L{headerNameAsBytes} encodes L{str} using L{HEADER_NAME_ENCODING}.
        """
        rawName = encodeName(name)
        self.assertEqual(headerNameAsBytes(name), rawName)

    @given(binary())
    def test_headerNameAsTextWithBytes(self, name: bytes) -> None:
        """
        L{headerNameAsText} decodes L{bytes} using L{HEADER_NAME_ENCODING}.
        """
        self.assertEqual(headerNameAsText(name), decodeName(name))

    @given(text(min_size=1))
    def test_headerNameAsTextWithText(self, name: str) -> None:
        """
        L{headerNameAsText} passes through L{str}.
        """
        self.assertIdentical(headerNameAsText(name), name)

    @given(binary())
    def test_headerValueAsBytesWithBytes(self, value: bytes) -> None:
        """
        L{headerValueAsBytes} passes through L{bytes}.
        """
        self.assertIdentical(headerValueAsBytes(value), value)

    @given(latin1_text(min_size=1))
    def test_headerValueAsBytesWithText(self, value: str) -> None:
        """
        L{headerValueAsBytes} encodes L{str} using L{HEADER_VALUE_ENCODING}.
        """
        rawValue = encodeValue(value)
        self.assertEqual(headerValueAsBytes(value), rawValue)

    @given(binary())
    def test_headerValueAsTextWithBytes(self, value: bytes) -> None:
        """
        L{headerValueAsText} decodes L{bytes} using L{HEADER_VALUE_ENCODING}.
        """
        self.assertEqual(headerValueAsText(value), decodeValue(value))

    @given(text(min_size=1))
    def test_headerValueAsTextWithText(self, value: str) -> None:
        """
        L{headerValueAsText} passes through L{str}.
        """
        self.assertIdentical(headerValueAsText(value), value)


class HeaderNameNormalizationTests(TestCase):
    """
    Tests for header name normalization.
    """

    def test_normalizeLowerCase(self) -> None:
        """
        L{normalizeHeaderName} normalizes header names to lower case.
        """
        self.assertEqual(normalizeHeaderName("FooBar"), "foobar")


class RawHeadersConversionTests(TestCase):
    """
    Tests for L{normalizeRawHeaders}.
    """

    def test_pairWrongLength(self) -> None:
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
    def test_pairNameText(self, name: str) -> None:
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
    def test_pairValueText(self, value: str) -> None:
        """
        L{normalizeRawHeaders} converts ISO-8859-1-encodable text values into
        bytes.
        """
        rawHeaders = ((b"name", value),)
        normalized = tuple(normalizeRawHeaders(rawHeaders))

        self.assertEqual(normalized, ((b"name", headerValueAsBytes(value)),))


class GetValuesTestsMixIn(ABC):
    """
    Tests for utilities that access data from the C{RawHeaders} internal
    representation.
    """

    @abstractmethod
    def getValues(
        self, rawHeaders: RawHeaders, name: AnyStr
    ) -> Iterable[AnyStr]:
        """
        Look up the values for the given header name from the given raw
        headers.

        This is called by the other tests in this mix-in class to allow test
        cases that use it to specify how to perform this look-up in the
        implementation being tested.
        """

    def test_getBytesName(self) -> None:
        """
        C{getValues} returns an iterable of L{bytes} values for the
        given L{bytes} header name.
        """
        rawHeaders = ((b"a", b"1"), (b"b", b"2"), (b"c", b"3"), (b"B", b"TWO"))

        normalized: Dict[bytes, List[bytes]] = defaultdict(list)
        for name, value in rawHeaders:
            normalized[normalizeHeaderName(name)].append(value)

        for name, values in normalized.items():
            cast(TestCase, self).assertEqual(
                list(self.getValues(rawHeaders, name)),
                values,
                f"header name: {name!r}",
            )

    def headerNormalize(self, value: str) -> str:
        """
        Test hook for the normalization of header text values, which is a
        behavior Twisted has changed after version 18.9.0.
        """
        return value

    @given(iterables(tuples(ascii_text(min_size=1), latin1_text())))
    def test_getTextName(self, textPairs: Iterable[Tuple[str, str]]) -> None:
        """
        C{getValues} returns an iterable of L{str} values for
        the given L{str} header name.

        This test only inserts Latin1 text into the header values, which is
        valid data.
        """
        textHeaders = tuple(
            (name, headerValueSanitize(value)) for name, value in textPairs
        )

        textValues: Dict[str, List[str]] = defaultdict(list)
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
                f"header name: {name!r}",
            )

    @given(iterables(tuples(ascii_text(min_size=1), binary())))
    def test_getTextNameBinaryValues(
        self, pairs: Iterable[Tuple[str, bytes]]
    ) -> None:
        """
        C{getValues} returns an iterable of L{str} values for
        the given L{str} header name.

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

        binaryValues: Dict[str, List[bytes]] = defaultdict(list)
        for name, value in rawHeaders:
            binaryValues[headerNameAsText(normalizeHeaderName(name))].append(
                value
            )

        for textName, values in binaryValues.items():
            cast(TestCase, self).assertEqual(
                tuple(self.getValues(rawHeaders, textName)),
                tuple(
                    self.headerNormalize(headerValueAsText(value))
                    for value in values
                ),
                f"header name: {textName!r}",
            )

    def test_getInvalidNameType(self) -> None:
        """
        C{getValues} raises L{TypeError} when the given header name is of an
        unknown type.
        """
        e = cast(TestCase, self).assertRaises(
            TypeError, self.getValues, (), object()
        )
        cast(TestCase, self).assertRegex(
            str(e), "name <object object at 0x[0-9a-f]+> must be str or bytes"
        )


class RawHeadersReadTests(GetValuesTestsMixIn, TestCase):
    """
    Tests for utilities that access data from the "headers tartare" internal
    representation.
    """

    def getValues(
        self, rawHeaders: RawHeaders, name: AnyStr
    ) -> Iterable[AnyStr]:
        return getFromRawHeaders(normalizeRawHeadersFrozen(rawHeaders), name)


class FrozenHTTPHeadersTests(GetValuesTestsMixIn, TestCase):
    """
    Tests for L{FrozenHTTPHeaders}.
    """

    def getValues(
        self, rawHeaders: RawHeaders, name: AnyStr
    ) -> Iterable[AnyStr]:
        headers = FrozenHTTPHeaders(rawHeaders=rawHeaders)
        return headers.getValues(name=name)

    def test_interface(self) -> None:
        """
        L{FrozenHTTPHeaders} implements L{IHTTPHeaders}.
        """
        headers = FrozenHTTPHeaders(rawHeaders=())
        self.assertProvides(IHTTPHeaders, headers)

    def test_defaultHeaders(self) -> None:
        """
        L{FrozenHTTPHeaders.rawHeaders} is empty by default.
        """
        headers = FrozenHTTPHeaders()
        self.assertEqual(headers.rawHeaders, ())


class MutableHTTPHeadersTestsMixIn(GetValuesTestsMixIn, ABC):
    """
    Tests for L{IMutableHTTPHeaders} implementations.
    """

    def assertRawHeadersEqual(
        self, rawHeaders1: RawHeaders, rawHeaders2: RawHeaders
    ) -> None:
        cast(TestCase, self).assertEqual(rawHeaders1, rawHeaders2)

    @abstractmethod
    def headers(self, rawHeaders: RawHeaders) -> IMutableHTTPHeaders:
        """
        Given a L{RawHeaders}, return an L{IMutableHTTPHeaders}.
        """

    def getValues(
        self, rawHeaders: RawHeaders, name: AnyStr
    ) -> Iterable[AnyStr]:
        headers = self.headers(rawHeaders=rawHeaders)
        return headers.getValues(name=name)

    def test_interface(self) -> None:
        """
        Class implements L{IMutableHTTPHeaders}.
        """
        headers = self.headers(rawHeaders=())
        cast(TestCase, self).assertProvides(IMutableHTTPHeaders, headers)

    def test_rawHeaders(self) -> None:
        """
        L{IMutableHTTPHeaders.rawHeaders} equals the raw headers passed at init
        time as a tuple.
        """
        rawHeaders = [(b"a", b"1"), (b"b", b"2"), (b"c", b"3")]
        headers = self.headers(rawHeaders=rawHeaders)
        self.assertRawHeadersEqual(headers.rawHeaders, tuple(rawHeaders))

    def test_removeBytesName(self) -> None:
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

    def test_removeTextName(self) -> None:
        """
        L{IMutableHTTPHeaders.remove} removes all values for the given L{str}
        header name.
        """
        rawHeaders = ((b"a", b"1"), (b"b", b"2a"), (b"c", b"3"), (b"b", b"2b"))
        headers = self.headers(rawHeaders=rawHeaders)
        headers.remove(name="b")

        self.assertRawHeadersEqual(
            headers.rawHeaders, ((b"a", b"1"), (b"c", b"3"))
        )

    def test_removeInvalidNameType(self) -> None:
        """
        L{IMutableHTTPHeaders.remove} raises L{TypeError} when the given header
        name is of an unknown type.
        """
        headers = self.headers(rawHeaders=())

        e = cast(TestCase, self).assertRaises(
            TypeError, headers.remove, object()
        )
        cast(TestCase, self).assertRegex(
            str(e), "name <object object at 0x[0-9a-f]+> must be str or bytes"
        )

    def test_addValueBytesName(self) -> None:
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

    def test_addValueTextName(self) -> None:
        """
        L{IMutableHTTPHeaders.addValue} adds the given L{str} value for the
        given L{str} header name.
        """
        rawHeaders = ((b"a", b"1"), (b"b", b"2a"))
        headers = self.headers(rawHeaders=rawHeaders)
        headers.addValue(name="b", value="2b")

        self.assertRawHeadersEqual(
            headers.rawHeaders, ((b"a", b"1"), (b"b", b"2a"), (b"b", b"2b"))
        )

    def test_addValueBytesNameTextValue(self) -> None:
        """
        L{IMutableHTTPHeaders.addValue} raises L{TypeError} when the given
        header name is L{bytes} and the given value is L{str}.
        """
        headers = self.headers(rawHeaders=())

        e = cast(TestCase, self).assertRaises(
            TypeError, headers.addValue, b"a", "1"
        )
        cast(TestCase, self).assertRegex(
            str(e), "value u?'1' must be bytes to match name b?'a'"
        )

    def test_addValueTextNameBytesValue(self) -> None:
        """
        L{IMutableHTTPHeaders.addValue} raises L{TypeError} when the given
        header name is L{str} and the given value is L{bytes}.
        """
        headers = self.headers(rawHeaders=())

        e = cast(TestCase, self).assertRaises(
            TypeError, headers.addValue, "a", b"1"
        )
        cast(TestCase, self).assertRegex(
            str(e), "value b?'1' must be str to match name u?'a'"
        )

    def test_addValueInvalidNameType(self) -> None:
        """
        L{IMutableHTTPHeaders.addValue} raises L{TypeError} when the given
        header name is of an unknown type.
        """
        headers = self.headers(rawHeaders=())

        e = cast(TestCase, self).assertRaises(
            TypeError, headers.addValue, object(), b"1"
        )
        cast(TestCase, self).assertRegex(
            str(e), "name <object object at 0x[0-9a-f]+> must be str or bytes"
        )


class MutableHTTPHeadersTests(MutableHTTPHeadersTestsMixIn, TestCase):
    """
    Tests for L{MutableHTTPHeaders}.
    """

    def headers(self, rawHeaders: RawHeaders) -> IMutableHTTPHeaders:
        return MutableHTTPHeaders(rawHeaders=rawHeaders)

    def test_defaultHeaders(self) -> None:
        """
        L{MutableHTTPHeaders.rawHeaders} is empty by default.
        """
        headers = MutableHTTPHeaders()
        self.assertEqual(headers.rawHeaders, ())
