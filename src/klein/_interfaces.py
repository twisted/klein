# Copyright (c) 2018. See LICENSE for details.

"""
Internal interface definitions.

All Zope Interface classes should be imported from here so that type checking
works, since mypy doesn't otherwise get along with Zope Interface.
"""

from typing import TYPE_CHECKING

from ._iapp import IKleinRequest
from ._imessage import (
    IHTTPHeaders as _IHTTPHeaders,
    IHTTPMessage as _IHTTPMessage,
    IHTTPRequest as _IHTTPRequest,
    IHTTPResponse as _IHTTPResponse,
    IMutableHTTPHeaders as _IMutableHTTPHeaders,
)

IKleinRequest  # Silence linter


if TYPE_CHECKING:               # pragma: no cover
    from typing import Union

    from ._headers import FrozenHTTPHeaders, MutableHTTPHeaders
    from ._headers_compat import HTTPHeadersWrappingHeaders
    from ._request import FrozenHTTPRequest
    from ._request_compat import HTTPRequestWrappingIRequest
    from ._response import FrozenHTTPResponse

    IHTTPHeaders = Union[
        _IHTTPHeaders,
        _IMutableHTTPHeaders,
        FrozenHTTPHeaders,
        HTTPHeadersWrappingHeaders,
        MutableHTTPHeaders,
    ]

    IMutableHTTPHeaders = Union[
        _IMutableHTTPHeaders,
        HTTPHeadersWrappingHeaders,
        MutableHTTPHeaders,
    ]

    IHTTPMessage = Union[
        _IHTTPMessage,
        _IHTTPRequest,
        _IHTTPResponse,
        FrozenHTTPRequest,
        FrozenHTTPResponse,
    ]

    IHTTPRequest = Union[
        _IHTTPRequest,
        FrozenHTTPRequest,
        HTTPRequestWrappingIRequest,
    ]

    IHTTPResponse = Union[
        _IHTTPResponse,
        FrozenHTTPResponse,
    ]

else:
    IHTTPHeaders        = _IHTTPHeaders
    IMutableHTTPHeaders = _IMutableHTTPHeaders
    IHTTPMessage        = _IHTTPMessage
    IHTTPRequest        = _IHTTPRequest
    IHTTPResponse       = _IHTTPResponse


__all__ = ()
