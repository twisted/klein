from __future__ import absolute_import, division

from zope.interface import Attribute, Interface


class IKleinRequest(Interface):
    branch_segments = Attribute("Segments consumed by a branch route.")
    mapper = Attribute("L{werkzeug.routing.MapAdapter}")

    def url_for(
        self, endpoint, values=None, method=None,
        force_external=False, append_unknown=True,
    ):
        """
        L{werkzeug.routing.MapAdapter.build}
        """
