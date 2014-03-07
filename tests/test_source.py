import ConfigParser
import re
import shlex
from StringIO import StringIO

import pilo

from . import TestCase


class ConfigPath(list):

    def __init__(self, src, *args, **kwargs):
        self.src = src
        super(ConfigPath, self).__init__(*args, **kwargs)

    def __str__(self):
        parts = []
        if self.src.file_path:
            parts.append(self.src.file_path)
        parts.append('[{0}]'.format(self.src.section))
        field = ''.join(([self[0]] + ['[{0}]'.format(f) for f in self[1:]]))
        parts.append(field)
        return ' '.join(parts)


class ConfigSource(pilo.Source):

    def __init__(self, config, section, file_path=None):
        super(ConfigSource, self).__init__()
        self.source = config
        self.section = section
        self.file_path = file_path
        self.parsers = {
            basestring: self._as_string,
            bool: self._as_boolean,
            int: self._as_integer,
            float: self._as_float,
        }

    def path(self, key=None):
        src_path = getattr(pilo.ctx, 'src_path', None)
        if src_path is None:
            src_path = ConfigPath(self)
        if key in (None, pilo.NONE):
            return src_path
        return ConfigPath(self, src_path + [key])

    def resolve(self, key):
        path = self.path(key)

        # option
        if len(path) == 1:
            option = path[0]
            if self.source.has_option(self.section, option):
                return option
            return pilo.NONE

        # container
        if len(path) == 2:
            option = '{0}[{1}]'.format(*path)
            if self.source.has_option(self.section, option):
                return option
            return pilo.NONE

        return pilo.NONE

    def sequence(self, key):
        if not self.source.has_option(self.section, key):
            return pilo.NONE
        raw = self.source.get(self.section, key)
        count = 0
        for i, value in enumerate(shlex.split(raw)):
            self.source.set(self.section, '{0}[{1}]'.format(key, i), value)
            count += 1
        return count

    def mapping(self, key):
        pattern = key + '\[(\w+)\]'
        keys = []
        for option in self.source.options(self.section):
            m = re.match(pattern, option)
            if not m:
                continue
            keys.append(m.group(1))
        if not keys:
            return pilo.NONE
        return keys


    def parse(self, key, option, type):
        value = self.source.get(self.section, option)
        if type is not None:
            value = self.parser_for(type)(key, value)
        return value



class TestCustomSource(TestCase):

    def test_configparser(self):

        class Settings(pilo.Form):

            state_dir = pilo.fields.String()

            backfill = pilo.fields.Bool()

            strict = pilo.fields.Bool()

            read_size = pilo.fields.Int().min(1024)

            buffer_size = pilo.fields.Int().min(1024)

            @buffer_size.validate
            def buffer_size(self, value):
                if value < self.read_size:
                    self.ctx.errors('"{0}" {1} must be > "{3}" {4}'.format(
                        type(self).read_size.src, value, type(self).read_size.source, self.read_size
                    ))
                    return False

            includes = pilo.fields.List(pilo.fields.String())


        parser = ConfigParser.ConfigParser()
        parser.readfp(StringIO("""\
[slurp]
state_dir = /var/lib/slurp
backfill = false
strict = false
read_size = 1024
buffer_size = 1048576
includes = /etc/slurp/conf.d/*.conf /etc/slurp/conf.d/*.py
"""
        ))
        src = ConfigSource(parser, 'slurp', '/spme/conf/file/ini')
        settings = Settings(src)
        self.assertDictEqual({
            'backfill': False,
            'read_size': 1024,
            'state_dir': '/var/lib/slurp',
            'strict': False,
            'includes': ['/etc/slurp/conf.d/*.conf', '/etc/slurp/conf.d/*.py'],
        }, settings)
