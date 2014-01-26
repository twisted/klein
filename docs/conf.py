import sys, os, re, codecs

here = os.path.abspath(os.path.dirname(__file__))

def read(*parts):
    return codecs.open(os.path.join(here, *parts), 'r').read()

def find_version(*file_paths):
    version_file = read(*file_paths)
    version_match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]",
                              version_file, re.M)
    if version_match:
        return version_match.group(1)
    raise RuntimeError("Unable to find version string.")

extensions = []
templates_path = ['_templates']
source_suffix = '.rst'
master_doc = 'index'
project = u'Klein'
copyright = u'2014, Twisted Matrix Labs'
version = find_version('..', 'klein', '__init__.py')
release = version
exclude_patterns = ['_build']
pygments_style = 'sphinx'
html_theme = 'default'

on_rtd = os.environ.get('READTHEDOCS', None) == 'True'
if not on_rtd:  # only import and set the theme if we're building docs locally
    import sphinx_rtd_theme
    html_theme = 'sphinx_rtd_theme'
    html_theme_path = [sphinx_rtd_theme.get_html_theme_path()]

html_static_path = ['_static']
htmlhelp_basename = 'Kleindoc'
latex_elements = {}
latex_documents = [
  ('index', 'Klein.tex', u'Klein Documentation',
   u'Twisted Matrix Labs', 'manual'),
]
man_pages = [
    ('index', 'klein', u'Klein Documentation',
     [u'Twisted Matrix Labs'], 1)
]
texinfo_documents = [
  ('index', 'Klein', u'Klein Documentation',
   u'Twisted Matrix Labs', 'Klein', 'One line description of project.',
   'Miscellaneous'),
]
