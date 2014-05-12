"""
"""
from . import Source, Path, ParserMixin, NONE


class DefaultPath(Path):

    def _resolve(self, container, atom):
        try:
            return container[atom]
        except (IndexError, KeyError, TypeError):
            try:
                return getattr(container, atom)
            except (AttributeError, TypeError):
                return NONE

    # Path

    def __init__(self, src, idx):
        super(DefaultPath, self).__init__(src, idx, src.data)

    def resolve(self, container, part):
        if isinstance(part, basestring) and part.endswith('()'):
            part = part[:-2]
            value = self.resolve(container, part)
            if value is NONE:
                return NONE
            return value()

        if isinstance(part, basestring):
            value = container
            for part in part.split('.'):
                value = self._resolve(value, part)
                if value is NONE:
                    break
        else:
            value = self._resolve(container, part)
        return value


class DefaultSource(Source, ParserMixin):

    def __init__(self, data):
        self.data = data

    # Source

    def path(self, idx):
        return DefaultPath(self, idx)

    def sequence(self, path):
        if not isinstance(path.value, (list, tuple)):
            raise self.error(path, 'is not a sequence')
        return len(path.value)

    def mapping(self, path):
        if not isinstance(path.value, (dict,)):
            raise self.error(path, 'is not a mapping')
        return path.value.keys()

    def primitive(self, path, *types):
        return self.parser(types)(self, path, path.value)
