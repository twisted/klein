def expose(url, *a, **kw):
    """
    Mark a ``KleinResource`` method as exposing a certain URL.

    URLs may have Werkzeug-style parameters in them, since they are
    essentially Werkzeug routes; see http://werkzeug.pocoo.org/docs/routing/
    for the details.

    >>> class SimpleResource(KleinResource):
    ...  @expose("/")
    ...  def index(self, request):
    ...   pass
    ...  @expose("/pages/<int:page_id>")
    ...  def pages(self, request, page_id):
    ...   pass

    Exposed methods will be called with at least two parameters. ``self`` is
    the explicit self. ``request`` is a ``twisted.web.request.Request``. The
    request will have two attributes: ``mapper``, the Werkzeug mapper used for
    the request, and ``url_for``, a callable which can build URLs for routes.
    """

    def deco(f):
        kw.setdefault('endpoint', f.__name__)
        f.__klein_exposed__ = url, a, kw
        return f
    return deco
