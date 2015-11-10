from klein import Klein


class NotFound(Exception):
    pass


class ItemStore(object):
    app = Klein()

    @app.handle_errors(NotFound)
    def notfound(self, request, failure):
        request.setResponseCode(404)
        return 'Not found, I say'

    @app.route('/droid/<string:name>')
    def droid(self, request, name):
        if name in ['R2D2', 'C3P0']:
            raise NotFound()
        return 'Droid found'

    @app.route('/bounty/<string:target>')
    def bounty(self, request, target):
        if target == 'Han Solo':
            return '150,000'
        raise NotFound()


if __name__ == '__main__':
    store = ItemStore()
    store.app.run('localhost', 8080)
