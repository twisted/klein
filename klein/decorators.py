def expose(url, *a, **kw):
    """
    Mark a ``KleinResource`` method as exposing a certain URL.

    URLs may have Werkzeug-style parameters in them, since they are
    essentially Werkzeug routes; see http://werkzeug.pocoo.org/docs/routing/
    for the details.

    >>> @expose("/")
    ... def index(self):
    ...  pass
    >>> @expose("/pages/<int:page_id>")
    ... def pages(self, page_id):
    ...  pass
    """

    def deco(f):
        kw.setdefault('endpoint', f.__name__)
        f.__klein_exposed__ = url, a, kw
        return f
    return deco
