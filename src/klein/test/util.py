"""
Shared tools for Klein's test suite.
"""

from abc import ABC, abstractmethod
from typing import TypeVar, cast

from treq.client import HTTPClient
from treq.testing import StubTreq as _StubTreq

from twisted.internet.defer import Deferred
from twisted.trial.unittest import SynchronousTestCase
from twisted.web.resource import IResource


class EqualityTestsMixin(ABC):
    """
    A mixin defining tests for the standard implementation of C{==} and C{!=}.
    """

    @abstractmethod
    def anInstance(self) -> object:
        """
        Return an instance of the class under test.  Each call to this method
        must return a different object.  All objects returned must be equal to
        each other.
        """

    @abstractmethod
    def anotherInstance(self) -> object:
        """
        Return an instance of the class under test.  Each call to this method
        must return a different object.  The objects must not be equal to the
        objects returned by C{anInstance}.  They may or may not be equal to
        each other (they will not be compared against each other).
        """

    def test_identicalEq(self) -> None:
        """
        An object compares equal to itself using the C{==} operator.
        """
        o = self.anInstance()
        cast(SynchronousTestCase, self).assertTrue(o == o)

    def test_identicalNe(self) -> None:
        """
        An object doesn't compare not equal to itself using the C{!=} operator.
        """
        o = self.anInstance()
        cast(SynchronousTestCase, self).assertFalse(o != o)

    def test_sameEq(self) -> None:
        """
        Two objects that are equal to each other compare equal to each other
        using the C{==} operator.
        """
        a = self.anInstance()
        b = self.anInstance()
        cast(SynchronousTestCase, self).assertTrue(a == b)

    def test_sameNe(self) -> None:
        """
        Two objects that are equal to each other do not compare not equal to
        each other using the C{!=} operator.
        """
        a = self.anInstance()
        b = self.anInstance()
        cast(SynchronousTestCase, self).assertFalse(a != b)

    def test_differentEq(self) -> None:
        """
        Two objects that are not equal to each other do not compare equal to
        each other using the C{==} operator.
        """
        a = self.anInstance()
        b = self.anotherInstance()
        cast(SynchronousTestCase, self).assertFalse(a == b)

    def test_differentNe(self) -> None:
        """
        Two objects that are not equal to each other compare not equal to each
        other using the C{!=} operator.
        """
        a = self.anInstance()
        b = self.anotherInstance()
        cast(SynchronousTestCase, self).assertTrue(a != b)

    def test_anotherTypeEq(self) -> None:
        """
        The object does not compare equal to an object of an unrelated type
        (which does not implement the comparison) using the C{==} operator.
        """
        a = self.anInstance()
        b = object()
        cast(SynchronousTestCase, self).assertFalse(a == b)

    def test_anotherTypeNe(self) -> None:
        """
        The object compares not equal to an object of an unrelated type (which
        does not implement the comparison) using the C{!=} operator.
        """
        a = self.anInstance()
        b = object()
        cast(SynchronousTestCase, self).assertTrue(a != b)

    def test_delegatedEq(self) -> None:
        """
        The result of comparison using C{==} is delegated to the right-hand
        operand if it is of an unrelated type.
        """

        class Delegate:
            def __eq__(self, other: object) -> bool:
                # Do something crazy and easily identifiable.
                return cast(bool, [self])

        a = self.anInstance()
        b = Delegate()
        cast(SynchronousTestCase, self).assertEqual(a == b, [b])

    def test_delegateNe(self) -> None:
        """
        The result of comparison using C{!=} is delegated to the right-hand
        operand if it is of an unrelated type.
        """

        class Delegate:
            def __ne__(self, other: object) -> bool:
                # Do something crazy and easily identifiable.
                return cast(bool, [self])

        a = self.anInstance()
        b = Delegate()
        cast(SynchronousTestCase, self).assertEqual(a != b, [b])


_T = TypeVar("_T")


def recover(d: "Deferred[_T]", exc_type: type[Exception]) -> "Deferred[_T]":
    return d.addErrback(lambda f: f.trap(exc_type))


class StubWithTypes(HTTPClient):
    def flush(self) -> bool:
        return True  # pragma: no cover


def makeStub(resource: IResource) -> StubWithTypes:
    """
    Create a StubTreq but give it a more convincing type signature.
    """
    return _StubTreq(resource)  # type:ignore[return-value]
