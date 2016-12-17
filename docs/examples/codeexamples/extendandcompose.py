from __future__ import unicode_literals
from functools import wraps
import json
from klein import Klein

class Jsonify(object):
    def __init__(self, router=None, secret=None):
        self.router = Klein() if not router else router
        self.secret = 'twisted-klein' if not secret else secret

    def route(self, url, *args, **kwargs):
        def deco(f):
            restricted = kwargs.pop('restricted', False)
            if restricted:
                f = self.authenticate(f)
            f = self.jsonify(f)
            self.router.route(url, *args, **kwargs)(f)
        return deco

    def jsonify(self, f):
        @wraps(f)
        def deco(*args, **kwargs):
            request = args[1]
            request.setHeader('Content-Type', 'application/json')
            return json.dumps(f(*args, **kwargs))
        return deco

    def authenticate(self, f):
        @wraps(f)
        def deco(*args, **kwargs):
            request = args[1]
            secret = request.getHeader('Authorization')
            if not secret or secret != self.secret:
                request.setResponseCode(401)
                body = {'access': 'denied'}
                return body
            return f(*args, **kwargs)
        return deco

class Application(object):
    router = Klein()
    json_api = Jsonify(router=router, secret='Tw!5t3d-kL3!n')

    @router.route('/')
    def hello(self, request):
        return 'Hello World'

    @json_api.route('/jsonify', methods=['GET'])
    def return_dict(self, request):
        return {'foo': 'bar'}

    @json_api.route('/admin', restricted=True)
    def admin(self, request):
        return {'access': 'granted'}

    @json_api.route('/alternate-admin')
    @json_api.authenticate
    def alternate(self, request):
        return {'access': 'granted (alternate)'}

if __name__=='__main__':
    app = Application()
    app.router.run('localhost', 8080)
