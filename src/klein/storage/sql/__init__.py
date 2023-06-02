"""
An implementation of a basic username/password authentication database using
C{dbxs}.
"""

from ._sql_glue import SQLSessionProcurer, authorizerFor


__all__ = [
    "SQLSessionProcurer",
    "authorizerFor",
]
