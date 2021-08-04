# Copyright (c) 2011-2021. See LICENSE for details.

"""
Internal interface definitions.

All Zope Interface classes should be imported from here so that type checking
works, since mypy doesn't otherwise get along with Zope Interface.
"""

from typing import Mapping, Optional, Union

from zope.interface import Attribute, Interface


KleinQueryValue = Union[str, int, float]


class IKleinRequest(Interface):
    branch_segments = Attribute("Segments consumed by a branch route.")
    mapper = Attribute("L{werkzeug.routing.MapAdapter}")

    def url_for(
        endpoint: str,
        values: Optional[Mapping[str, KleinQueryValue]] = None,
        method: Optional[str] = None,
        force_external: bool = False,
        append_unknown: bool = True,
    ) -> str:
        """
        L{werkzeug.routing.MapAdapter.build}
        """


__all__ = ()
