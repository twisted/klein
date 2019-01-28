# Copyright (c) 2017-2018. See LICENSE for details.

"""
Extensions to L{twisted.trial}.
"""

import sys
from typing import Any

from twisted import version as twistedVersion
from twisted.trial.unittest import SynchronousTestCase

from zope.interface import Interface
from zope.interface.exceptions import Invalid
from zope.interface.verify import verifyObject

Any, Interface  # Silence linter


__all__ = ()



class TestCase(SynchronousTestCase):
    """
    Extensions to L{SynchronousTestCase}.
    """

    if (twistedVersion.major, twistedVersion.minor) < (16, 4):
        def assertRegex(self, text, regex, msg=None):
            # type: (str, Any, str) -> None
            """
            Fail the test if a C{regexp} search of C{text} fails.

            @param text: Text which is under test.

            @param regex: A regular expression object or a string containing a
                regular expression suitable for use by re.search().

            @param msg: Text used as the error message on failure.
            """
            if sys.version_info[:2] > (2, 7):
                super(TestCase, self).assertRegex(text, regex, msg)
            else:
                # Python 2.7 has unittest.assertRegexpMatches() which was
                # renamed to unittest.assertRegex() in Python 3.2
                super(TestCase, self).assertRegexpMatches(text, regex, msg)


    def assertProvides(self, interface, obj):
        # type: (Interface, Any) -> None
        """
        Assert that a object provides an interface.

        @param interface: The interface the object is expected to provide.
        @param obj: The object to test.
        """
        try:
            self.assertTrue(verifyObject(interface, obj))
        except Invalid:
            self.fail("{} does not provide {}".format(obj, interface))
