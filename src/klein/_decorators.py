from functools import wraps

def bindable(bindable):
    """
    Mark a method as a "bindable" method.

    If a L{Klein.app} resource is found on an instance object (i.e. is returned
    from C{YourObject().app.resource()}), it will pass C{self} from that
    instance to all of its routes, making a signature of 2 arguments: C{self}
    and C{request} However, if it's found globally (i.e. C{app = Klein()};
    C{@app.route(...)} at global scope), then it will only receive one:
    C{request}.  However, for decorators that must be able to live between
    C{@route} and the user's function, but still need to manipulate the
    C{request} object, they need to be invoked with a consistent argument
    signature.  A method decorated with C{@klein_bindable} will therefore
    always take C{instance, request} as its first two arguments, even if
    C{instance} is C{None} when the L{Klein} object is not bound to an
    instance.

    @return: its argument, modified to mark it as unconditinally requiring an
        instance argument.
    """
    bindable.__klein_bound__ = True
    return bindable


def modified(modification, original):
    """
    Annotate a callable as a modified wrapper of an original callable.

    @param modification: A name for the type of modification, for example "form
        processor" or "request forwarder"; this will be tacked on to the name
        of the resulting function.

    @return: A new callable; this may have a different argument signature or
        return value, and is only related to C{original} in the sense that it
        likely calls it.
    """
    def decorator(wrapper):
        return (named(modification + ' for ' + original.__name__)
                (wraps(original, updated=[])(wrapper)))
    return decorator


def named(name):
    """
    Change the name of a function to the given name.
    """
    def decorator(original):
        original.__name__ = str(name)
        return original
    return decorator
