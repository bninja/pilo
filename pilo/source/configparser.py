"""
"""
import collections
import re
import shlex

from . import Source, Path, ParserMixin, NONE


class ConfigPath(Path):

    def __init__(self, src):
        super(ConfigPath, self).__init__(src)
        self.location = src.location
        self.section = src.section
        self.parts = []
        if src.section:
            self.root = SectionMapping(src.config, src.section)
        else:
            self.root = Mapping(src.config)

    @property
    def value(self):
        if not self.parts:
            return self.root
        try:
            value = self.root[self.parts[0]]
            for part in self.parts[1:]:
                if isinstance(value, basestring):
                    value = Sequence(value)
                value = value[part]
        except (KeyError, IndexError, TypeError):
            return NONE
        return value

    def __str__(self):
        parts = []
        if self.location:
            parts.append(self.location)
        if self.section:
            parts.append('[{0}]'.format(self.section))
        parts.append(super(ConfigPath, self).__str__())
        return ':'.join(parts)

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


class Sequence(collections.Sequence):

    def __init__(self, value):
        self.values = shlex.split(value)

    def __getitem__(self, i):
        return self.values[i]

    def __len__(self):
        return len(self.values)


class SectionMapping(collections.Mapping):

    def __init__(self, config, section):
        self.config = config
        self.section = section
        pattern = r'(?P<name>\w+)\[(?P<key>\w+)\]'
        self.sub_mappings = collections.defaultdict(dict)
        for option, value in self.config.items(section):
            m = re.match(pattern, option)
            if not m:
                continue
            self.sub_mappings[m.group('name')][m.group('key')] = value

    def __getitem__(self, key):
        if key in self.sub_mappings:
            return self.sub_mappings[key]
        if self.config.has_option(self.section, key):
            return self.config.get(self.section, key)
        raise KeyError(key)

    def __iter__(self):
        for k, v in self.sub_mappings.iteritems():
            yield k, v
        for k, v in self.config.items(self.section):
            yield k, v

    def __len__(self):
        return len(self.sub_mappings) + len(self.config.options(self.section))


class Mapping(collections.Mapping):

    def __init__(self, config, section=None):
        self.config = config
        self.section = section

    def __getitem__(self, key):
        if not self.config.has_section(key):
            raise KeyError(key)
        return SectionMapping(self.config, key)

    def __iter__(self):
        for section in self.config.sections():
            yield section, SectionMapping(self.config, section)

    def __len__(self):
        return len(self.config.sections())


class ConfigSource(Source, ParserMixin):

    def __init__(self, config, section=None, location=None):
        super(ConfigSource, self).__init__()
        self.config = config
        self.section = section
        self.location = location

    # Source

    def path(self):
        return ConfigPath(self)

    def sequence(self, path):
        value = path.value
        if value is NONE:
            from ipdb import set_trace; set_trace()
        if isinstance(value, basestring):
            return len(Sequence(value))
        raise self.error(path, 'not a sequence')

    def mapping(self, path):
        if isinstance(path.value, (collections.Mapping, dict)):
            return path.value.keys()
        raise self.error(path, 'not a mapping')

    def primitive(self, path, type=None):
        return self.parser(type)(self, path, path.value)
