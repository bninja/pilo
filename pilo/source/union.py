import collections

from . import Path, Source, NONE


class UnionPath(Path):

    def __init__(self, src):
        self.paths = [s.path() for s in src.srcs]
        super(UnionPath, self).__init__(src, Mapping(src, self.paths, 'combine'))

    # Path

    def resolve(self, container, part):
        try:
            return container[part.key]
        except (IndexError, KeyError, TypeError):
            return NONE

    # collections.MutableSequence

    def __setitem__(self, index, value):
        super(UnionPath, self).__setitem__(index, value)
        for path in self.paths:
            path[index] = value

    def __delitem__(self, index):
        super(UnionPath, self).__delitem__(index)
        for path in self.paths:
            del path[index]

    def insert(self, index, value):
        super(UnionPath, self).insert(index, value)
        for path in self.paths:
            path.insert(index, value)


class UnionSource(Source):

    def __init__(self,
                 srcs,
                 merge='first',
                 mapping_merge=None,
                 sequence_merge=None,
                 merge_depth=None,
        ):
        super(UnionSource, self).__init__()
        self.srcs = srcs
        self.mapping_merge = mapping_merge or merge
        self.sequence_merge = sequence_merge or merge
        self.merge_depth = merge_depth

    # Source

    def path(self):
        return UnionPath(self)

    def mapping(self, path):
        if isinstance(path.value, Join):
            path.value = path.value.mapping()
        if isinstance(path.value, Mapping):
            return path.value.keys()
        raise self.error(path, 'not a mapping')

    def sequence(self, path):
        if isinstance(path.value, Join):
            path.value = path.value.sequence()
        if isinstance(path.value, Sequence):
            return len(path.value)
        raise self.error(path, 'not a sequence')

    def primitive(self, path, *types):
        if isinstance(path.value, Join):
            path.value = path.value.primitive(*types)
        return path.value


class Join(object):

    def __init__(self, src, paths):
        self.src = src
        self.paths = paths

    def mapping(self):
        return Mapping(self.src, self.paths)

    def sequence(self):
        return Sequence(self.src, self.paths)

    def primitive(self, *types):
        if not self.paths:
            return NONE
        return self.paths[0].primitive(*types)


class Mapping(collections.Mapping):

    def __init__(self, src, paths, merge=None):
        mappings = []
        for path in paths:
            if not path.exists or path.is_null:
                continue
            keys = path.mapping()
            if not mappings:
                mappings.append((path, keys))
                continue
            if merge is None:
                merge = src.mapping_merge
                if src.merge_depth is not None and src.merge_depth <= len(path):
                    merge = 'first'
            if merge == 'combine':
                mappings.append((path, keys))
            elif merge == 'first':
                pass
            elif merge == 'last':
                mappings[0] = (path, keys)
            else:
                raise ValueError('merge="{1}" invalid'.format(merge))
        self.src = src
        self.mappings = mappings

    # collections.Mapping

    def __getitem__(self, key):
        paths = []
        for path, keys in self.mappings:
            if key in keys:
                paths.append(path)
        if not paths:
            raise KeyError(key)
        return Join(self.src, paths)

    def __len__(self):
        keys = (key for _, mapping in self.mappings for key in mapping)
        return len(list(set(keys)))

    def __iter__(self):
        keys = (key for _, mapping in self.mappings for key in mapping)
        return iter(list(set(keys)))


class Sequence(collections.Sequence):

    def __init__(self, src, paths, merge=None):
        sequences = []
        for path in paths:
            if not path.exists or path.is_null:
                continue
            length = path.sequence()
            if not sequences:
                sequences.append((path, length))
                continue
            if merge is None:
                merge = src.sequence_merge
                if src.merge_depth is not None and src.merge_depth <= len(path):
                    merge = 'first'
            if merge == 'combine':
                sequences.append((path, length))
            elif merge == 'first':
                pass
            elif merge == 'last':
                sequences[0] = (path, length)
            else:
                raise ValueError('merge="{1}" invalid'.format(merge))
        self.src = src
        self.sequences = sequences

    # collections.Sequence

    def __getitem__(self, key):
        offset = 0
        for path, length in self.sequences:
            if key < offset + length:
                break
            offset += length
        else:
            raise IndexError(key)
        path[-1].key -= offset
        return Join(self.src, [path])

    def __len__(self):
        return sum(length for _, length in self.sequences)
