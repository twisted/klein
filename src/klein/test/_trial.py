# Copyright (c) 2011-2021. See LICENSE for details.

"""
Extensions to L{twisted.trial}.
"""

from typing import Type

from zope.interface import Interface
from zope.interface.exceptions import Invalid
from zope.interface.verify import verifyObject

from twisted.trial.unittest import SynchronousTestCase


__all__ = ()


class TestCase(SynchronousTestCase):
    """
    Extensions to L{SynchronousTestCase}.
    """

    def assertProvides(self, interface: Type[Interface], obj: object) -> None:
        """
        Assert that a object provides an interface.

        @param interface: The interface the object is expected to provide.
        @param obj: The object to test.
        """
        try:
            self.assertTrue(verifyObject(interface, obj))
        except Invalid:
            self.fail(f"{obj} does not provide {interface}")
