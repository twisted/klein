from zope.interface import Attribute, Interface

from ._typing import ifmethod



class IKleinRequest(Interface):
    branch_segments = Attribute("Segments consumed by a branch route.")
    mapper = Attribute("L{werkzeug.routing.MapAdapter}")

    @ifmethod
    def url_for(
        self, endpoint, values=None, method=None,
        force_external=False, append_unknown=True,
    ):
        """
        L{werkzeug.routing.MapAdapter.build}
        """
