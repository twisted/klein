# -*- test-case-name: klein.test.test_request -*-
# Copyright (c) 2011-2021. See LICENSE for details.

"""
HTTP request API.
"""

from typing import Union

from attr import Factory, attrib, attrs
from attr.validators import instance_of, provides
from hyperlink import DecodedURL
from tubes.itube import IFount
from zope.interface import implementer

from ._imessage import IHTTPHeaders, IHTTPRequest
from ._message import MessageState, bodyAsBytes, bodyAsFount, validateBody


__all__ = ()


@implementer(IHTTPRequest)
@attrs(frozen=True)
class FrozenHTTPRequest:
    """
    Immutable HTTP request.
    """

    method: str = attrib(validator=instance_of(str))
    uri: DecodedURL = attrib(validator=instance_of(DecodedURL))
    headers: IHTTPHeaders = attrib(validator=provides(IHTTPHeaders))

    _body: Union[bytes, IFount] = attrib(validator=validateBody)

    _state: MessageState = attrib(default=Factory(MessageState), init=False)

    def bodyAsFount(self) -> IFount:
        return bodyAsFount(self._body, self._state)

    async def bodyAsBytes(self) -> bytes:
        return await bodyAsBytes(self._body, self._state)
