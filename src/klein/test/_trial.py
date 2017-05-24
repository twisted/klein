# -*- test-case-name: klein.test.test_request -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Extensions to L{twisted.trial}.
"""

from twisted.trial.unittest import SynchronousTestCase as _TestCase

from zope.interface.exceptions import Invalid
from zope.interface.verify import verifyObject


__all__ = ()



class TestCase(_TestCase):
    """
    Extensions to L{TestCase}.
    """

    def assertProvides(self, interface, obj):
        """
        Assert that a object provides an interface.

        @param interface: The interface the object is expected to provide.
        @param obj: The object to test.
        """
        try:
            self.assertTrue(verifyObject(interface, obj))
        except Invalid as e:
            self.fail("{} does not provide {}".format(obj, interface))
