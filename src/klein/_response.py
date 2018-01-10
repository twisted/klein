# -*- test-case-name: klein.test.test_response -*-
# Copyright (c) 2017-2018. See LICENSE for details.

"""
HTTP response API.
"""

from typing import Union

from attr import Factory, attrib, attrs
from attr.validators import instance_of, provides

from tubes.itube import IFount

from twisted.internet.defer import Deferred

from zope.interface import Attribute, implementer

from ._headers import IHTTPHeaders
from ._message import (
    IHTTPMessage, MessageState, bodyAsBytes, bodyAsFount, validateBody
)

Deferred, IFount, Union  # Silence linter


__all__ = ()



class IHTTPResponse(IHTTPMessage):
    """
    HTTP response.
    """

    status = Attribute("Response status code.")  # type: int



@implementer(IHTTPResponse)
@attrs(frozen=True)
class FrozenHTTPResponse(object):
    """
    Immutable HTTP response.
    """

    status = attrib(validator=instance_of(int))  # type: int

    headers = attrib(validator=provides(IHTTPHeaders))  # type: IHTTPHeaders

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
