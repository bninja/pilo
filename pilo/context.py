"""
There is a global, thread-local instance of `Context`, `ctx`, used to:

- track source (i.e. parse) and destination (i.e. form) paths in parallel
- and a stack of variables (e.g. `ctx.variables`)

Source and destination paths are managed like:

    .. code:: python

        print ctx.src_path, ctx.src_depth
        print ctx.dst_path, ctx.dst_depth
        with ctx.push('dst', 'src'):
            print ctx.src_path, ctx.src_depth
        print ctx.dst_path, ctx.dst_depth

and `Context` variables are are managed like:

    .. code:: python

        with ctx(my_var=123):
            print ctx.my_var
        try:
            ctx.my_var
        except AttributeError:
            pass

"""
import functools
import threading

from . import NONE


class Frame(object):

    def __init__(self, **kwargs):
        self._values = kwargs

    def _copy(self, **kwargs):
        values = self._values.copy()
        values.update(kwargs)
        return type(self)(**values)

    def __getattr__(self, k):
        if k in self._values:
            return self._values[k]
        raise AttributeError('"{0}" object has no attribute "{1}"'.format(
            type(self).__name__, k
        ))


class Close(object):

    def __init__(self, func):
        self.func = func

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.func()


class DestinationPath(list):

    def push(self, part):
        self.append(part)
        return Close(self.pop)

    def __str__(self):
        if not self:
            return ''
        parts = [self[0]]
        for part in self[1:]:
            if isinstance(part, int):
                part = '[{0}]'.format(int)
            else:
                part = '.' + part
            parts.append(part)
        return ''.join(parts)


class Context(threading.local):
    """
    Used to manage:

    - a stack of variable `Frame`
    - paths with a source and destination (i.e. form).

    You should never need to create this, just use the `ctx` global.
    """

    def __init__(self):
        threading.local.__init__(self)
        self.stack = [Frame(src=None)]
        self.dst_path = DestinationPath()

    def __getattr__(self, k):
        for frame in reversed(self.stack):
            if hasattr(frame, k):
                return getattr(frame, k)
        raise AttributeError('"{0}" object has no attribute "{1}"'.format(
            self.__class__.__name__, k
        ))

    def __call__(self, **kwargs):
        self.stack.append(Frame(**kwargs))
        return Close(self.stack.pop)

    def reset(self):
        """
        Used if you need to recursively parse forms.
        """
        dst_path = self.dst_path
        self.dst_path = []
        self.stack.append(Frame(src=None))
        return Close(functools.partial(self.restore, dst_path))

    def restore(self, dst_path):
        self.dst_path = dst_path
        self.stack.pop()

    @property
    def dst_depth(self):
        return len(self.dst_path)

    @property
    def src_depth(self):
        return len(self.src_path)


#: Global thread-local context.
ctx = Context()


class ContextMixin(object):
    """
    Mixin used to add a convenience `.ctx` property.
    """

    @property
    def ctx(self):
        return ctx
