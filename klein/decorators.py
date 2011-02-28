def expose(url, *a, **kw):
    def deco(f):
        kw.setdefault('endpoint', f.__name__)
        f.__klein_exposed__ = url, a, kw
        return f
    return deco
