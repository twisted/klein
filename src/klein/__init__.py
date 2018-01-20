from __future__ import absolute_import, division

from ._app import Klein, handle_errors, resource, route, run, urlFor, url_for
from ._form import Field, Form
from ._plating import Plating
from ._session import SessionProcurer
from ._version import __version__ as _incremental_version


__all__ = (
    "Klein",
    "Plating",
    'Field',
    'Form',
    'SessionProcurer',
    "__author__",
    "__copyright__",
    "__license__",
    "__version__",
    "handle_errors",
    "resource",
    "route",
    "run",
    "urlFor",
    "url_for",
)


# Make it a str, for backwards compatibility
__version__ = _incremental_version.base()

__author__ = "The Klein contributors (see AUTHORS)"
__license__ = "MIT"
__copyright__ = "Copyright 2016-2017 {0}".format(__author__)
