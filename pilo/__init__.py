"""
"""
__version__ = '0.3.0'

__all__ = [
    'adapt',
    'NOT_SET',
    'NONE',
    'ERROR',
    'IGNORE',
    'ctx',
    'fields',
    'Field',
    'Form',
    'Source',
    'SourceError',
    'DefaultPath',
    'DefaultSource',
    'ParseError',
]


class _Constant(object):

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return '{0}("{1}")'.format(type(self).__name__, self.name)


NOT_SET = _Constant('NOT_SET')

NONE = _Constant('NONE')

ERROR = _Constant('ERROR')

IGNORE = (NONE, ERROR, NOT_SET)

from . import source
from .source import Source, SourceError, DefaultPath, DefaultSource
from .context import ctx, ContextMixin, DummyClose
from . import fields
from .fields import Field, FieldError, Form
