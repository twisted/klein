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
        self.users = {
            "frank": "hunter2",
            "marry": "strong_password",
            "amanda": "twisted12"
        }

    @app.route("/login")
    def login_page(self, equest):
        template = self.templates.get_template("login.html")
        return template.render()

    @app.route("/do_login", methods=["POST"])
    def do_login(self, request):
        username = request.args.get(b"username")
        password = request.args.get(b"password")
        if not username or not password:
            request.setResponseCode(400)
            return
        username = username[0].decode("utf8")
        password = password[0].decode("utf8")
        saved_password = self.users.get(username)
        if not saved_password:
            request.setResponseCode(403)
            return
        if saved_password != password:
            request.setResponseCode(403)
            return
        session_id = request.getSession().uid
        self.sessions[session_id] = username
        request.redirect("/")
        return b""

    @app.route("/static/<filename>")
    def static(self, request, filename):
        return File(path.join("static", filename))


if __name__ == "__main__":
    my_app = MyApp(db_name="books.db")
    my_app.app.run("localhost", 8080)
