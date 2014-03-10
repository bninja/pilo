"""
A `Source` where a `Form` "maps" (resolves, parses, etc) values from. There is
a default `IdentitySource` which we use to talk to native pthon container types:

- dicts
- lists
- tuples

and primitives (e.g. int, basestring, etc). But typically you will implement
`Source` for your source e.g.:

- application/api+json mime string
- ConfigParser.ConfigParser object
- ...

"""
import collections
import inspect

from .. import ctx, ContextMixin, NONE
from contextlib import contextmanager

__all__ = [
    'Error',
    'Path',
    'Source',
    'DefaultSource',
    'ConfigSource',
]


class SourceError(Exception):
    """
    Based class for all `Source` path resolve errors.
    """

    def __init__(self, path, message):
        super(SourceError, self).__init__(message)
        self.path = path
        self.message = message


class Path(collections.Sequence):
    """
    Represents a path to a `Field` within a `Source`.
    """

    def __init__(self, src):
        self.src = src

    def __str__(self):
        parts = []
        if self:
            parts = ['{0}'.format(self[0])]
            for part in self[1:]:
                if isinstance(part, int):
                    part = '[{0}]'.format(part)
                else:
                    part = '.' + part
                parts.append(part)
        return ''.join(parts)

    class close(object):

        def __init__(self, func):
            self.func = func

        def __enter__(self):
            pass

        def __exit__(self, exc_type, exc_value, traceback):
            self.func()

    def __copy__(self):
        instance = type(self)(self.src)
        for part in self:
            instance.push(part)
        return instance

    # Path

    @property
    def exists(self):
        raise NotImplementedError()

    @property
    def is_null(self):
        raise NotImplementedError()

    def push(self, name):
        raise NotImplementedError()

    def pop(self):
        raise NotImplementedError()

    def primitive(self, type=None):
        return self.src.primitive(self, type)

    def sequence(self):
        return self.src.sequence(self)

    def mapping(self):
        return self.src.mapping(self)

    # collections.Sequence


class Source(ContextMixin):
    """
    Interface for creating paths and resolving them to primitives:

        - string
        - integer
        - float

    and optionally containers:

        - sequence
        - mapping

    within a source (e.g. MIME string, ConfigParser object, etc).
    """

    #: Used to construct an error when resolving a path for this source fails.
    error = SourceError

    def path(self):
        """
        Constructs a root path for this source.
        """
        raise NotImplementedError()

    def mapping(self, path):
        """
        Resolves a path to a mapping within this source.
        """
        raise NotImplementedError('{0} does not support mappings!'.format(type(self)))

    def sequence(self, path):
        """
        Resolves a path to a sequence within this source.
        """
        raise NotImplementedError('{0} does not support sequences!'.format(type(self)))

    def primitive(self, path, type=None):
        """
        Resolves a path to a primitive within this source. If no type is given
        then it'll be inferred if possible.
        """
        raise NotImplementedError()


class ParserMixin(object):
    """
    Mixin for adding simple parsing capabilities to a `Source`.
    """

    def as_string(self, path, value):
        if isinstance(value, basestring):
            return value
        raise self.error(path, '"{0}" is not a string'.format(value))

    def as_int(self, path, value):
        if isinstance(value, (int, long)) and not isinstance(value, bool):
            pass
        elif isinstance(value, float):
            if not value.is_integer():
                raise self.error(path, '"{0}" is not an integer'.format(value))
            else:
                value = int(value)
        elif isinstance(value, basestring):
            try:
                value = int(value)
            except (ValueError, TypeError):
                raise self.error(path, '"{0}" is not an integer'.format(value))
        else:
            raise self.error(path, '"{0}" is not an integer'.format(value))
        return value

    def as_float(self, path, value):
        if isinstance(value, (float)):
            pass
        elif isinstance(value, (int, long)):
            value = float(value)
        elif isinstance(value, basestring):
            try:
                value = float(value)
            except (ValueError, TypeError):
                raise self.error(path, '"{0}" is not a float'.format(value))
        else:
            raise self.error(path, '"{0}" is not a float'.format(value))
        return value

    def as_bool(self, path, value):
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return value != 0
        if isinstance(value, basestring):
            if value.lower() in ('0', 'f', 'false'):
                return False
            elif value.lower() in ('1', 't', 'true'):
                return True
        raise self.error(path, '"{0}" is not a boolean'.format(value))

    def as_auto(self, path, value):
        return value

    parsers = {
        basestring: as_string,
        int: as_int,
        float: as_float,
        bool: as_bool,
        None: as_auto,
    }

    def parser(self, types, default=NONE):
        if not isinstance(types, (tuple, list)):
            types = [types]
        for t in types:
            if t in self.parsers:
                return self.parsers[t]
            for mro_t in inspect.getmro(t):
                if mro_t in self.parsers:
                    self.parsers[t] = self.types[mro_t]
                    return self.parsers[t]
        if default is not NONE:
            return default
        raise ValueError('No parser for type {0}'.format(t))


from .default import DefaultSource
from .configparser import ConfigSource
from .json import JsonSource
