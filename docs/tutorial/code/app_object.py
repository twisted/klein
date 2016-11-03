from jinja2 import Environment, PackageLoader
from klein import Klein


class MyApp(object):
    app = Klein()

    def __init__(self, db_name):
        loader = PackageLoader("templates", package_path="")
        templates = Environment(loader=loader)
        self.templates = templates
        self.db_name = db_name
        self.sessions = {}

    @app.route("/")
    def home(self, request):
        pass

    @app.route("/login")
    def login_page(self, equest):
        pass

    @app.route("/do_login", methods=["POST"])
    def do_login(self, request):
        pass

    @app.route("/book/<key>")
    def book(self, request, key):
        pass

    @app.route("/static/<filename>")
    def static(self, request, filename):
        pass


if __name__ == "__main__":
    my_app = MyApp(db_name="books.db")
    my_app.app.run("localhost", 8080)
