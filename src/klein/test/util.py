"""
Shared tools for Klein's test suite.
"""

from typing import Generic, Protocol, TypeVar, cast

from twisted.trial.unittest import SynchronousTestCase


T_co = TypeVar("T_co", covariant=True)


class EqualityTestProtocol(Protocol[T_co], SynchronousTestCase):
    def anInstance(self) -> T_co:
        """
        Return an instance of the class under test.  Each call to this method
        must return a different object.  All objects returned must be equal to
        each other.
        """

    def anotherInstance(self) -> T_co:
        """
        Return an instance of the class under test.  Each call to this method
        must return a different object.  All objects returned must be equal to
        each other.
        """


class EqualityTestsMixin(Generic[T_co]):
    """
    A mixin defining tests for the standard implementation of C{==} and C{!=}.
    """

    def test_identicalEq(self: EqualityTestProtocol[T_co]) -> None:
        """
        An object compares equal to itself using the C{==} operator.
        """
        o = self.anInstance()
        self.assertTrue(o == o)

    def test_identicalNe(self: EqualityTestProtocol[T_co]) -> None:
        """
        An object doesn't compare not equal to itself using the C{!=} operator.
        """
        o = self.anInstance()
        self.assertFalse(o != o)

    def test_sameEq(self: EqualityTestProtocol[T_co]) -> None:
        """
        Two objects that are equal to each other compare equal to each other
        using the C{==} operator.
        """
        a = self.anInstance()
        b = self.anInstance()
        self.assertTrue(a == b)

    def test_sameNe(self: EqualityTestProtocol[T_co]) -> None:
        """
        Two objects that are equal to each other do not compare not equal to
        each other using the C{!=} operator.
        """
        a = self.anInstance()
        b = self.anInstance()
        self.assertFalse(a != b)

    def test_differentEq(self: EqualityTestProtocol[T_co]) -> None:
        """
        Two objects that are not equal to each other do not compare equal to
        each other using the C{==} operator.
        """
        a = self.anInstance()
        b = self.anotherInstance()
        self.assertFalse(a == b)

    def test_differentNe(self: EqualityTestProtocol[T_co]) -> None:
        """
        Two objects that are not equal to each other compare not equal to each
        other using the C{!=} operator.
        """
        a = self.anInstance()
        b = self.anotherInstance()
        self.assertTrue(a != b)

    def test_anotherTypeEq(self: EqualityTestProtocol[T_co]) -> None:
        """
        The object does not compare equal to an object of an unrelated type
        (which does not implement the comparison) using the C{==} operator.
        """
        a = self.anInstance()
        b = object()
        self.assertFalse(a == b)

    def test_anotherTypeNe(self: EqualityTestProtocol[T_co]) -> None:
        """
        The object compares not equal to an object of an unrelated type (which
        does not implement the comparison) using the C{!=} operator.
        """
        a = self.anInstance()
        b = object()
        self.assertTrue(a != b)

    def test_delegatedEq(self: EqualityTestProtocol[T_co]) -> None:
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
        self.assertEqual(a == b, [b])

    def test_delegateNe(self: EqualityTestProtocol[T_co]) -> None:
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
        self.assertEqual(a != b, [b])
