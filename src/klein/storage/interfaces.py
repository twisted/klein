
from typing import TYPE_CHECKING, Union

from ._istorage import ISQLAuthorizer as _ISQLAuthorizer

if TYPE_CHECKING:
    from ._sql import SimpleSQLAuthorizer
    ISQLAuthorizer = Union[_ISQLAuthorizer, SimpleSQLAuthorizer]
else:
    ISQLAuthorizer = _ISQLAuthorizer

__all__ = [
    'ISQLAuthorizer'
]
