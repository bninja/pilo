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
from __future__ import unicode_literals
import inspect

from . import NONE, ctx, ContextMixin


class ParseError(ValueError):

    def __init__(self, key, message):
        super(ParseError, self).__init__(message)
        self.path = ctx.src.path(key)
        self.message = message


class Source(ContextMixin):
    """
    Abstraction of a source from with to map values.
    """

    # interface

    #: A list-like type used to represent a path in your source. You'll also
    #: want to override __str__ to give helpful diagnostics.
    path_type = None

    def path(self, key):
        """
        Should return and instance of `path_type` for a key. It will typically
        be constructed from `ctx.src_path` for nested `Source`s.
        """
        raise NotImplementedError()

    def resolve(self, key):
        """
        Resolve source key (taking into account `ctx.src_path` for nested
        `Source`s) to something to later pass along to `parse`. 
        """
        raise NotImplementedError()

    def sequence(self, key):
        """
        Resolve source key as a sequence to something to later pass along to
        `parse`.
        """
        raise NotImplementedError()

    def mapping(self, key):
        """
        Resolve source key as a mapping to something to later pass along to
        `parse`.
        """
        raise NotImplementedError()

    def parse(self, key, resolved, type):
        """
        Parse a key, for which `resolve` resolved, as `type`.   
        """
        raise NotImplementedError()

    # helpers

    parsers = None

    def parser_for(self, types, default=NONE):
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
        raise TypeError('No parser for type {}'.format(t))

    def no_parser_error(self, t):
        return TypeError('Invalid type {}, expecting one of {}'.format(
            t, self.parsers.keys()
        ))

    def __getitem__(self, key):
        v = self.resolve(key)
        if v is NONE:
            raise KeyError(key)
        return v

    def __contains__(self, key):
        return self.resolve(key) != NONE

    def _as_string(self, key, value):
        if not isinstance(value, basestring):
            value = str(value)
        return value

    def _as_integer(self, key, value):
        if isinstance(value, (int, long)) and not isinstance(value, bool):
            pass
        elif isinstance(value, float):
            if not value.is_integer():
                raise ParseError(key, '"{0}" is not an integer'.format(value))
            else:
                value = int(value)
        elif isinstance(value, basestring):
            try:
                value = int(value)
            except (ValueError, TypeError):
                raise ParseError(key, '"{0}" is not an integer'.format(value))
        else:
            raise ParseError(key, '"{0}" is not an integer'.format(value))
        return value

    def _as_float(self, key, value):
        if isinstance(value, (float)):
            pass
        elif isinstance(value, (int, long)):
            value = float(value)
        elif isinstance(value, basestring):
            try:
                value = float(value)
            except (ValueError, TypeError):
                raise ParseError(key, '"{0}" is not a float'.format(value))
        else:
            raise ParseError(key, '"{0}" is not a float'.format(value))
        return value

    def _as_boolean(self, key, value):
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return value == 0
        if isinstance(value, basestring):
            if value.lower() in ('0', 'f', 'false'):
                return False
            elif value.lower() in ('1', 't', 'true'):
                return True
        raise ParseError(key, '"{0}" is not a boolean'.format(value))


IdentityPath = list


class IdentitySource(Source):

    def __init__(self, source):
        self.source = source
        self.parsers = {
            basestring: self._as_string,
            bool: self._as_boolean,
            int: self._as_integer,
            float: self._as_float,
        }

    def path(self, key=None):
        src_path = getattr(ctx, 'src_path', None)
        if src_path is None:
            src_path = IdentityPath()
        if key in (None, NONE):
            return src_path
        return IdentityPath(src_path + [key])

    def resolve(self, key):
        s = self.source
        try:
            for part in self.path(key):
                s = s[part]
        except (TypeError, KeyError, IndexError):
            return NONE
        return s

    def sequence(self, key):
        s = self.source
        try:
            for part in self.path(key):
                s = s[part]
        except (TypeError, KeyError, IndexError):
            return NONE
        if not isinstance(s, (list, tuple)):
            raise ParseError(key, '"{0}" is not a sequence'.format(self.path(key)))
        return len(s)

    def mapping(self, key):
        s = self.source
        try:
            for part in self.path(key):
                s = s[part]
        except (TypeError, KeyError, IndexError):
            return NONE
        if not isinstance(s, dict):
            raise ParseError(key, '"{0}" is not a mapping'.format(self.path(key)))
        return s.keys()

    def parse(self, key, resolved, type):
        if type is None:
            return resolved
        return self.parser_for(type)(key, resolved)
