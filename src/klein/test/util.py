"""
Shared tools for Klein's test suite.
"""

import twisted
from twisted.python import failure
from twisted.python.versions import Version
from twisted.trial.unittest import TestCase



if twisted.version < Version('twisted', 13, 1, 0):
    class TestCase(TestCase):
        def successResultOf(self, deferred):
            result = []
            deferred.addBoth(result.append)

            if not result:
                self.fail(
                    "Success result expected on {!r}, found no result instead"
                    .format(deferred)
                )

            if isinstance(result[0], failure.Failure):
                self.fail(
                    "Success result expected on {!r}, "
                    "found failure result instead:\n{}"
                    .format(deferred, result[0].getTraceback())
                )

            return result[0]

        def failureResultOf(self, deferred, *expectedExceptionTypes):
            result = []
            deferred.addBoth(result.append)

            if not result:
                self.fail(
                    "Failure result expected on {!r}, found no result instead"
                    .format(deferred)
                )

            if not isinstance(result[0], failure.Failure):
                self.fail(
                    "Failure result expected on {!r}, "
                    "found success result ({!r}) instead"
                    .format(deferred, result[0])
                )

            if (
                expectedExceptionTypes and
                not result[0].check(*expectedExceptionTypes)
            ):
                expectedString = " or ".join([
                    '.'.join((t.__module__, t.__name__))
                    for t in expectedExceptionTypes
                ])

                self.fail(
                    "Failure of type ({}) expected on {!r}, "
                    "found type {!r} instead: {}"
                    .format(
                        expectedString, deferred, result[0].type,
                        result[0].getTraceback()
                    )
                )

            return result[0]



class EqualityTestsMixin(object):
    """
    A mixin defining tests for the standard implementation of C{==} and C{!=}.
    """
    def anInstance(self):
        """
        Return an instance of the class under test.  Each call to this method
        must return a different object.  All objects returned must be equal to
        each other.
        """
        raise NotImplementedError()


    def anotherInstance(self):
        """
        Return an instance of the class under test.  Each call to this method
        must return a different object.  The objects must not be equal to the
        objects returned by C{anInstance}.  They may or may not be equal to
        each other (they will not be compared against each other).
        """
        raise NotImplementedError()


    def test_identicalEq(self):
        """
        An object compares equal to itself using the C{==} operator.
        """
        o = self.anInstance()
        self.assertTrue(o == o)


    def test_identicalNe(self):
        """
        An object doesn't compare not equal to itself using the C{!=} operator.
        """
        o = self.anInstance()
        self.assertFalse(o != o)


    def test_sameEq(self):
        """
        Two objects that are equal to each other compare equal to each other
        using the C{==} operator.
        """
        a = self.anInstance()
        b = self.anInstance()
        self.assertTrue(a == b)


    def test_sameNe(self):
        """
        Two objects that are equal to each other do not compare not equal to
        each other using the C{!=} operator.
        """
        a = self.anInstance()
        b = self.anInstance()
        self.assertFalse(a != b)


    def test_differentEq(self):
        """
        Two objects that are not equal to each other do not compare equal to
        each other using the C{==} operator.
        """
        a = self.anInstance()
        b = self.anotherInstance()
        self.assertFalse(a == b)


    def test_differentNe(self):
        """
        Two objects that are not equal to each other compare not equal to each
        other using the C{!=} operator.
        """
        a = self.anInstance()
        b = self.anotherInstance()
        self.assertTrue(a != b)


    def test_anotherTypeEq(self):
        """
        The object does not compare equal to an object of an unrelated type
        (which does not implement the comparison) using the C{==} operator.
        """
        a = self.anInstance()
        b = object()
        self.assertFalse(a == b)


    def test_anotherTypeNe(self):
        """
        The object compares not equal to an object of an unrelated type (which
        does not implement the comparison) using the C{!=} operator.
        """
        a = self.anInstance()
        b = object()
        self.assertTrue(a != b)


    def test_delegatedEq(self):
        """
        The result of comparison using C{==} is delegated to the right-hand
        operand if it is of an unrelated type.
        """
        class Delegate(object):
            def __eq__(self, other):
                # Do something crazy and obvious.
                return [self]

        a = self.anInstance()
        b = Delegate()
        self.assertEqual(a == b, [b])


    def test_delegateNe(self):
        """
        The result of comparison using C{!=} is delegated to the right-hand
        operand if it is of an unrelated type.
        """
        class Delegate(object):
            def __ne__(self, other):
                # Do something crazy and obvious.
                return [self]

        a = self.anInstance()
        b = Delegate()
        self.assertEqual(a != b, [b])
