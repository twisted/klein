# -*- test-case-name: klein.test.test_plating -*-

from functools import wraps
import json

class Plating(object):
    """
    
    """
    def __init__(self, *a, **k):
        """
        
        """

    def content(self, *args):
        """
        
        """
        def decorator(arg):
            @wraps(arg)
            def wrapper(*args, **kwargs):
                return json.dumps(arg(*args, **kwargs))
            return wrapper
        return decorator
