"""
Sphinx/docutils extension to create links to pyDoctor documentation using a
RestructuredText interpreted text role that looks like this::

    :api:`python_object_to_link_to <label>`

for example::

    :api:`twisted.internet.defer.Deferred <Deferred>`

"""

from types import MappingProxyType


apilinks_base_url = "https://docs.twisted.org/en/stable/api/"

emptyMapping = MappingProxyType({})


def make_api_link(
    name,
    rawtext,
    text,
    lineno,
    inliner,
    options=emptyMapping,
    content=(),
):
    from docutils import nodes, utils

    # quick, dirty, and ugly...
    if "<" in text and ">" in text:
        full_name, label = text.split("<")
        full_name = full_name.strip()
        label = label.strip(">").strip()
    else:
        full_name = text

    # not really sufficient, but just testing...
    # ...hmmm, maybe this is good enough after all
    ref = "".join((apilinks_base_url, full_name, ".html"))

    node = nodes.reference(
        rawtext, utils.unescape(label), refuri=ref, **options
    )

    nodes = [node]
    sys_msgs = []
    return nodes, sys_msgs


# setup function to register the extension


def setup(app):
    app.add_config_value(
        "apilinks_base_url",
        "https://docs.twisted.org/en/stable/api/",
        "env",
    )
    app.add_role("api", make_api_link)
