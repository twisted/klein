import importlib.machinery
import importlib.util
import os
import sys


def load_source(modname, filename):
    loader = importlib.machinery.SourceFileLoader(modname, filename)
    spec = importlib.util.spec_from_file_location(
        modname, filename, loader=loader
    )
    module = importlib.util.module_from_spec(spec)
    # The module is always executed and not cached in sys.modules.
    # Uncomment the following line to cache the module.
    # sys.modules[module.__name__] = module
    loader.exec_module(module)
    return module


# Add the extensions folder...
sys.path.insert(0, os.path.abspath("./_extensions"))

_version = load_source("setup", "../src/klein/_version.py")

extensions = []
templates_path = ["_templates"]
source_suffix = ".rst"
master_doc = "index"
project = "Klein"
copyright = "2011-2022, Twisted Matrix Labs"
version = _version.__version__.base()
release = version
exclude_patterns = ["_build"]
pygments_style = "sphinx"
html_theme = "default"

on_rtd = os.environ.get("READTHEDOCS", None) == "True"
if not on_rtd:  # only import and set the theme if we're building docs locally
    import sphinx_rtd_theme

    html_theme = "sphinx_rtd_theme"
    html_theme_path = [sphinx_rtd_theme.get_html_theme_path()]

htmlhelp_basename = "Kleindoc"
latex_elements = {}
latex_documents = [
    (
        "index",
        "Klein.tex",
        "Klein Documentation",
        "Twisted Matrix Labs",
        "manual",
    ),
]
man_pages = [
    ("index", "klein", "Klein Documentation", ["Twisted Matrix Labs"], 1)
]
texinfo_documents = [
    (
        "index",
        "Klein",
        "Klein Documentation",
        "Twisted Matrix Labs",
        "Klein",
        "One line description of project.",
        "Miscellaneous",
    ),
]

# API links extension, stolen from Twisted's Sphinx setup
extensions.append("apilinks")
apilinks_base_url = "https://docs.twisted.org/en/stable/api/"
