from functools import wraps
from typing import Callable, Iterable, Tuple, TypeVar


T = TypeVar("T")
S = TypeVar("S")


def given(
    parameters: Callable[[], Iterable[T]]
) -> Callable[[Callable[[S, T], None]], Callable[[S], None]]:
    def decorator(testMethod: Callable[[S, T], None]) -> Callable[[S], None]:
        @wraps(testMethod)
        def realTestMethod(self: S) -> None:
            for parameter in parameters():
                testMethod(self, parameter)

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
            "latin1-text",
            "some more latin1 text",
            "hére is latin1 text",
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


def text(min_size: int = 0) -> Callable[[], Iterable[str]]:
    """
    Generate some text.
    """

    def params() -> Iterable[str]:
        yield from latin1_text(min_size)()
        yield "\N{SNOWMAN}"

    return params


def textHeaderPairs() -> Callable[[], Iterable[Iterable[Tuple[str, str]]]]:
    """ """


def bytesHeaderPairs() -> Callable[[], Iterable[Iterable[Tuple[str, bytes]]]]:
    """ """
