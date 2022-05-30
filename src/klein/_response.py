# -*- test-case-name: klein.test.test_response -*-
# Copyright (c) 2011-2021. See LICENSE for details.

"""
HTTP response API.
"""

from typing import Union

from attr import Factory, attrib, attrs
from attr.validators import instance_of, provides
from tubes.itube import IFount
from zope.interface import implementer

from ._imessage import IHTTPHeaders, IHTTPResponse
from ._message import MessageState, bodyAsBytes, bodyAsFount, validateBody


__all__ = ()


@implementer(IHTTPResponse)
@attrs(frozen=True)
class FrozenHTTPResponse:
    """
    Immutable HTTP response.
    """

    status: int = attrib(validator=instance_of(int))

    headers: IHTTPHeaders = attrib(validator=provides(IHTTPHeaders))

    _body: Union[bytes, IFount] = attrib(validator=validateBody)

    _state: MessageState = attrib(default=Factory(MessageState), init=False)

    def bodyAsFount(self) -> IFount:
        return bodyAsFount(self._body, self._state)

    async def bodyAsBytes(self) -> bytes:
        return await bodyAsBytes(self._body, self._state)
