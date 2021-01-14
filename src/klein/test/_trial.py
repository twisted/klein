# Copyright (c) 2011-2021. See LICENSE for details.

"""
Extensions to L{twisted.trial}.
"""

from typing import Any

from twisted.trial.unittest import SynchronousTestCase

from zope.interface import Interface
from zope.interface.exceptions import Invalid
from zope.interface.verify import verifyObject


__all__ = ()


class TestCase(SynchronousTestCase):
    """
    Extensions to L{SynchronousTestCase}.
    """

    def assertProvides(self, interface: Interface, obj: Any) -> None:
        """
        Assert that a object provides an interface.

        @param interface: The interface the object is expected to provide.
        @param obj: The object to test.
        """
        try:
            self.assertTrue(verifyObject(interface, obj))
        except Invalid:
            self.fail(f"{obj} does not provide {interface}")
