from __future__ import unicode_literals
from functools import wraps
import json
from klein import Klein

class Jsonify(object):
    def __init__(self, app=None, secret=None):
        self.app = Klein() if not app else app
        self.secret = 'twisted-klein' if not secret else secret

    def route(self, url, *args, **kwargs):
        def deco(f):
            restricted = kwargs.pop('restricted', False)
            if restricted:
                f = self.authenticate(f)
            f = self.jsonMiddleware(f)
            self.app.route(url, *args, **kwargs)(f)
        return deco

    def jsonMiddleware(self, f):
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

class Main(object):
    app = Klein()
    jsonApp = Jsonify(app=app, secret='Tw!5t3d-kL3!n')

    @app.route('/')
    def hello(self, request):
        return 'Hello World'

    @jsonApp.route('/jsonify', methods=['GET'])
    def jsonify(self, request):
        return {'foo': 'bar'}

    @jsonApp.route('/admin', restricted=True)
    def admin(self, request):
        return {'access': 'granted'}

    @jsonApp.route('/alternate-admin')
    @jsonApp.authenticate
    def alternate(self, request):
        return {'access': 'granted (alternate)'}

if __name__=='__main__':
    main = Main()
    main.app.run('localhost', 8080)
