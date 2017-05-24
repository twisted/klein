# -*- test-case-name: klein.test.test_request -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
HTTP headers.
"""

from zope.interface import Interface


__all__ = ()



# Interfaces

class IHTTPHeaders(Interface):
    """
    HTTP entity headers.
    """
