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

import inspect


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
from .context import ctx, ContextMixin, Close
from . import fields
from .fields import Field, FieldError, Form


class Identities(dict):

    @classmethod
    def map(cls, field):

        def _map(form_cls):
            if not inspect.isabstract(object):
                try:
                    value = getattr(form_cls(), field.name)
                    identities[value] = form_cls
                except AttributeError:
                    pass
            for sub_cls in form_cls.__subclasses__():
                _map(sub_cls)

        if not isinstance(field, Field):
            raise TypeError('Excepted field')

        if not field.is_attached:
            raise ValueError('{} is not attached'.format(field))

        identities = cls.for_field(field)
        _map(field.parent)
        return identities

    @classmethod
    def for_field(cls, id_field):
        fields = {}
        for field in id_field.parent.fields:
            fields[field.name] = type(field)(field.src, default=None)
            if field is id_field:
                break
        else:
            raise ValueError('No {0} in {1}'.format(id_field, id_field.parent))
        probe_form = type('Probe', (Form,), fields)
        return cls(probe_form, id_field)

    def __init__(self, probe_form, id_field):
        self.probe_form = probe_form
        self.id_field = id_field

    def __getitem__(self, key):
        return dict.__getitem__(self, key)

    def probe(self, src, default=NONE):
        probe = self.probe_form()
        errors = probe.map(src)
        if not errors:
            return getattr(probe, self.id_field.name)
        if default in IGNORE:
            raise errors[0]
        return default
