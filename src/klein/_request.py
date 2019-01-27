# -*- test-case-name: klein.test.test_request -*-
# Copyright (c) 2017-2018. See LICENSE for details.

"""
HTTP request API.
"""

from typing import Text, Union

from attr import Factory, attrib, attrs
from attr.validators import instance_of, provides

from hyperlink import DecodedURL

from tubes.itube import IFount

from twisted.internet.defer import Deferred

from zope.interface import implementer

from ._interfaces import IHTTPHeaders, IHTTPRequest
from ._message import MessageState, bodyAsBytes, bodyAsFount, validateBody

# Silence linter
Deferred, IFount, IHTTPHeaders, Text, Union


__all__ = ()



@implementer(IHTTPRequest)
@attrs(frozen=True)
class FrozenHTTPRequest(object):
    """
    Immutable HTTP request.
    """

    method  = attrib(validator=instance_of(Text))        # type: Text
    uri     = attrib(validator=instance_of(DecodedURL))  # type: DecodedURL
    headers = attrib(validator=provides(IHTTPHeaders))   # type: IHTTPHeaders

    _body = attrib(validator=validateBody)  # type: Union[bytes, IFount]

    _state = attrib(
        default=Factory(MessageState), init=False
    )  # type: MessageState


    def bodyAsFount(self):
        # type: () -> IFount
        return bodyAsFount(self._body, self._state)


    def bodyAsBytes(self):
        # type: () -> Deferred[bytes]
        return bodyAsBytes(self._body, self._state)
