import os
import sys
import vcversioner

# Add the extensions folder...
sys.path.insert(0, os.path.abspath('./_extensions'))

extensions = []
templates_path = ['_templates']
source_suffix = '.rst'
master_doc = 'index'
project = u'Klein'
copyright = u'2015, Twisted Matrix Labs'
version = release = vcversioner.find_version(root='..').version
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
    ('index', 'klein',
     u'Klein Documentation',
     [u'Twisted Matrix Labs'],
     1),
]
texinfo_documents = [
    ('index', 'Klein', u'Klein Documentation',
     u'Twisted Matrix Labs', 'Klein',
     'twisted + werkzeug',
     'Miscellaneous'),
]

# API links extension, stolen from Twisted's Sphinx setup
extensions.append('apilinks')
apilinks_base_url = 'https://twistedmatrix.com/documents/current/api/'
