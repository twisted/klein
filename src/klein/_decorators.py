def bindable(bindable):
    """
    Mark a method as a "bindable" method.

    If a L{Klein.app} resource is found on an instance object (i.e. is returned
    from C{YourObject().app.resource()}), it will pass C{self} from that
    instance to all of its routes, making a signature of 2 arguments::

        self, request

    However, if it's found globally (i.e. C{app = Klein(); @app.route(...)} at
    global scope), then it will only receive one: C{request}.  However, for
    decorators that must be able to live between C{@route} and the user's
    function, but still need to manipulate the C{request} object, they need to
    be invoked with a consistent argument signature.  A method decorated with
    C{@klein_bindable} will therefore always take C{instance, request} as its
    first two arguments, even if C{instance} is C{None} when the L{Klein}
    object is not bound to an instance.

    @return: its argument, modified to mark it as unconditinally requiring an
        instance argument.
    """
    bindable.__klein_bound__ = True
    return bindable


