"""
We have had a history of U{bad
experiences<https://github.com/twisted/klein/issues/561>} with Hypothesis in
Klein, and maybe it's not actually a good application of this tool at all.  As
such we have removed it, at least for now.  This module presents a vaguely
Hypothesis-like stub, to keep the structure of our tests in a
Hypothesis-friendly shape, in case we want to put it back.
"""

from functools import wraps
from itertools import product
from string import ascii_uppercase
from typing import Callable, Iterable, Optional, Tuple, TypeVar

from hyperlink import DecodedURL, parse as parseURL


T = TypeVar("T")
S = TypeVar("S")


def given(
    *args: Callable[[], Iterable[T]],
    **kwargs: Callable[[], Iterable[T]],
) -> Callable[[Callable[..., None]], Callable[..., None]]:
    def decorator(testMethod: Callable[..., None]) -> Callable[..., None]:
        @wraps(testMethod)
        def realTestMethod(self: S) -> None:
            everyPossibleArgs = product(
                *[eachFactory() for eachFactory in args]
            )
            everyPossibleKwargs = product(
                *[
                    [(name, eachValue) for eachValue in eachFactory()]
                    for (name, eachFactory) in kwargs.items()
                ]
            )
            everyPossibleSignature = product(
                everyPossibleArgs, everyPossibleKwargs
            )
            # not quite the _full_ cartesian product but the whole point is
            # that we're making a feeble attempt at this rather than bringing
            # in hypothesis.
            for (computedArgs, computedPairs) in everyPossibleSignature:
                computedKwargs = dict(computedPairs)
                testMethod(self, *computedArgs, **computedKwargs)

        return realTestMethod

    return decorator


def binary() -> Callable[[], Iterable[bytes]]:
    """
    Generate some binary data.
    """

    def params() -> Iterable[bytes]:
        return [b"data", b"data data data", b"\x00" * 50]

    return params


def ascii_text(min_size: int = 0) -> Callable[[], Iterable[str]]:
    """
    Generate some ASCII strs.
    """

    def params() -> Iterable[str]:
        yield from [
            "ascii-text",
            "some more ascii text",
        ]
        if not min_size:
            yield ""

    return params


def latin1_text(min_size: int = 0) -> Callable[[], Iterable[str]]:
    """
    Generate some strings encodable as latin1
    """

    def params() -> Iterable[str]:
        yield from [
            "latin1-text",
            "some more latin1 text",
            "hére is latin1 text",
        ]
        if not min_size:
            yield ""

    return params


def text(
    min_size: int = 0, alphabet: Optional[str] = None
) -> Callable[[], Iterable[str]]:
    """
    Generate some text.
    """

    def params() -> Iterable[str]:
        if alphabet == ascii_uppercase:
            yield from ascii_text()()
            return
        yield from latin1_text(min_size)()
        yield "\N{SNOWMAN}"

    return params


def textHeaderPairs() -> Callable[[], Iterable[Iterable[Tuple[str, str]]]]:
    """
    Generate some pairs of headers with text values.
    """

    def params() -> Iterable[Iterable[Tuple[str, str]]]:
        return [[], [("text", "header")]]

    return params


def bytesHeaderPairs() -> Callable[[], Iterable[Iterable[Tuple[str, bytes]]]]:
    """
    Generate some pairs of headers with bytes values.
    """

    def params() -> Iterable[Iterable[Tuple[str, bytes]]]:
        return [[], [("bytes", b"header")]]

    return params


def booleans() -> Callable[[], Iterable[bool]]:
    def parameters() -> Iterable[bool]:
        yield True
        yield False

    return parameters


def jsonObjects() -> Callable[[], Iterable[object]]:
    def parameters() -> Iterable[object]:
        yield {}
        yield {"hello": "world"}
        yield {"here is": {"some": "nesting"}}
        yield {
            "and": "multiple",
            "keys": {
                "with": "nesting",
                "and": 1234,
                "numbers": ["with", "lists", "too"],
            },
        }

    return parameters


def decoded_urls() -> Callable[[], Iterable[DecodedURL]]:
    """
    Generate a few URLs U{with only path and domain names
    <https://github.com/python-hyper/hyperlink/issues/181>} kind of like
    Hyperlink's own hypothesis strategy.
    """

    def parameters() -> Iterable[DecodedURL]:
        yield DecodedURL.from_text("https://example.com/")
        yield DecodedURL.from_text("https://example.com/é")
        yield DecodedURL.from_text("https://súbdomain.example.com/ascii/path/")

    return parameters
