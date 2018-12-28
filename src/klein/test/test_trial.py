# Copyright (c) 2017-2018. See LICENSE for details.

"""
Tests for L{klein.test._trial}.
"""

from zope.interface import Interface, implementer

from ._trial import TestCase


__all__ = ()



class TestCaseTests(TestCase):
    """
    Tests for L{TestCase}.
    """

    class IFrobbable(Interface):
        """
        Frobbable object.
        """
        def frob():
            # type: () -> None
            """
            Frob the object.
            """


    @implementer(IFrobbable)
    class Frobbable(object):
        """
        Implements L{IFrobbable}.
        """
        def frob(self):
            # type: () -> None
            pass


    @implementer(IFrobbable)
    class NotFrobbable(object):
        """
        Does not implement L{IFrobbable}, despite declaring.
        """


    def test_assertProvidesPass(self):
        # type: () -> None
        """
        L{TestCase.assertProvides} does not raise when C{interface} is provided
        by C{obj}.
        """
        frobbable = self.Frobbable()
        self.assertProvides(self.IFrobbable, frobbable)
        frobbable.frob()  # Coverage


    def test_assertProvidesFail(self):
        # type: () -> None
        """
        L{TestCase.assertProvides} does not raise when C{interface} is not
        provided by C{obj}.
        """
        self.assertRaises(
            self.failureException,
            self.assertProvides, self.IFrobbable, self.NotFrobbable(),
        )
