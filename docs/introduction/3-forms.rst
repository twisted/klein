
HTML Forms and Dependency Injection
===================================

In :ref:`“Streamlined Apps With HTML and JSON” <htmljson>` we set up a basic
site that could render HTML and read data.  However, for most applications, you
will need some way for users to input data; in other words: handling forms,
both rendering them and posting them.

In order to handle forms `securely
<https://owasp.org/www-community/attacks/csrf>`_, we also have to implement
some form of authenticated session along with them.

So let's build on top of our food-list application by letting users submit a
form that adds some foods to a list.
