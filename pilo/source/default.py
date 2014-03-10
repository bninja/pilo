"""
"""
from . import Source, Path, ParserMixin, NONE


class DefaultPath(Path):

    def __init__(self, src):
        super(DefaultPath, self).__init__(src)
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


class DefaultSource(Source, ParserMixin):

    def __init__(self, data):
        self.data = data

    # Source

    def path(self):
        return DefaultPath(self)

    def sequence(self, path):
        if not isinstance(path.value, (list, tuple)):
            raise self.error(path, 'is not a sequence')
        return len(path.value)

    def mapping(self, path):
        if not isinstance(path.value, (dict,)):
            raise self.error(path, 'is not a mapping')
        return path.value.keys()

    def primitive(self, path, type=None):
        return self.parser(type)(self, path, path.value)
