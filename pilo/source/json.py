"""
"""
from __future__ import absolute_import

import inspect
import json

from . import Source, Path, NONE


class JsonPath(Path):

    def __init__(self, src, location=None):
        super(JsonPath, self).__init__(src)
        self.location = location
        self.container = src.data
        self.parts = []

    @property
    def value(self):
        value = self.container
        try:
            for part in self:
                value = value[part]
        except (IndexError, KeyError, TypeError):
            return NONE
        return value

    def __str__(self):
        value = super(JsonPath, self).__str__()
        if self.location:
            value = '{0}:{1}'.format(self.location, value)
        return value

    # Path

    @property
    def exists(self):
        return self.value is not NONE

    @property
    def is_null(self):
        return self.value is None

    def push(self, name):
        self.parts.append(name)
        return self.close(self.pop)

    def pop(self):
        self.parts.pop()

    # collections.Sequence

    def __getitem__(self, key):
        return self.parts[key]

    def __len__(self):
        return len(self.parts)


class JsonSource(Source):

    def __init__(self, text, strict=False, location=None):
        super(Source, self).__init__()
        self.strict = strict
        self.location = location
        self.text = text
        self.data = json.loads(text)

    def as_string(self, field, value):
        if not isinstance(value, basestring):
            value = str(value)
        raise self.error(field, '{0} is not a string'.format(value))

    def as_int(self, field, value):
        if isinstance(value, (int, long)) and not isinstance(value, bool):
            return value
        if not self.strict:
            if isinstance(value, float) and value.is_integer():
                return int(value)
        raise self.error(field, '{0} is not an integer'.format(value))

    def as_float(self, field, value):
        if isinstance(value, (float)):
            return value
        if isinstance(value, (int, long)):
            return float(value)
        raise self.error(field, '{0} is not a float'.format(value))

    def as_bool(self, field, value):
        if isinstance(value, bool):
            return value
        if not self.strict:
            if isinstance(value, int):
                return value != 0
        raise self.error(field, '{0} is not a boolean'.format(value))

    def as_auto(self, field, value):
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

    # Source

    def path(self):
        return JsonPath(self, self.location)

    def sequence(self, path):
        if path.name not in path.container:
            return None
        container = path.token[path.name]
        if not isinstance(container, (list, tuple)):
            raise self.error(path, 'not a sequence')
        return path

    def mapping(self, path):
        if path.name not in path.container:
            return None
        value = path.token[path.name]
        if not isinstance(value, (dict,)):
            raise self.error(path, 'not a mapping')
        return path

    def primitive(self, path, type=None):
        return self.parser(type)(self, path, path.value)
