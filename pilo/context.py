"""
There is a global, thread-local instance of `Context`, `ctx`, used to:

- track source (i.e. parse) paths
- and a stack of variables (e.g. `ctx.variables`)

Source and destination paths are managed like:

    .. code:: python

        print ctx.src_path
        with ctx.push(src='src'):
            print ctx.src_path

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

from . import Source, NOT_SET


class Frame(dict):

    def __getattr__(self, k):
        if k in self:
            return self[k]
        raise AttributeError('"{0}" object has no attribute "{1}"'.format(
            self.__class__.__name__, k
        ))


class DummyContext(object):

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        pass


class Close(object):

    dummy = DummyContext()

    def __init__(self, func):
        self.func = func

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.func()


class RewindDidNotStop(Exception):

    def __init__(self):
        super(RewindDidNotStop, self).__init__(
            'Did not reach unwind stop condition'
        )


class SourcePart(object):

    def __init__(self, key):
        self.key = key
        self.value = NOT_SET

    def __str__(self):
        return str(self.key)



class Context(threading.local):
    """
    Used to manage variables and source paths with these reserved attributes:

    `src`
        TODO

    `src_path`
        TODO

    `src_idx`
        TODO

    You should never need to create this, just use the `ctx` global.
    """

    RewindDidNotStop = RewindDidNotStop

    def __init__(self):
        threading.local.__init__(self)
        self.stack = [
            Frame(src=None, src_path=None, src_idx=None),
        ]

    def __getattr__(self, k):
        for frame in reversed(self.stack):
            if k in frame:
                return frame[k]
        raise AttributeError('"{0}" object has no attribute "{1}"'.format(
            self.__class__.__name__, k
        ))

    def values_for(self, k):
        """
        Each value with name `k`.
        """
        return [getattr(frame, k) for frame in self.stack if hasattr(frame, k)]

    def reset(self):
        """
        Used if you need to recursively parse forms.
        """
        self.stack.append(Frame(src=None, src_path=None, src_idx=None))
        return Close(functools.partial(self.restore))

    def rewind(self, stop):
        """
        Used if you need to rewind stack to a particular frame.

        :param predicate: Callable used to stop unwind, e.g.:

            .. code::

                def stop(frame):
                    return True

        :return: A context object used to restore the stack.
        """
        for i, frame in enumerate(reversed(self.stack)):
            if stop(frame):
                frames = self.stack[-i:]
                break
        else:
            raise RewindDidNotStop()
        del self.stack[-i:]
        if self.src_idx is not None:
            for frame in frames:
                if 'src_idx' in frame:
                    break
                if 'src' in frame:
                    self.src_idx.pop()
        return Close(functools.partial(self.restore, frames))

    def push(self, **kwargs):
        """
        """
        if 'src' in kwargs:
            if isinstance(kwargs['src'], Source):
                kwargs['src_idx'] = []
                kwargs['src_path'] = kwargs['src'].path(kwargs['src_idx'])
            else:
                kwargs['src'] = SourcePart(kwargs['src'])
                self.src_idx.append(kwargs['src'])
        self.stack.append(Frame(**kwargs))
        return Close(self.restore)

    #: Alias for `push`.
    __call__ = push

    def restore(self, frames=None):
        """
        """
        if frames is None:
            frame = self.stack.pop()
            if 'src' in frame and 'src_idx' not in frame:
                self.src_idx.pop()
        elif frames:
            if self.src_idx is not None:
                for frame in frames:
                    if 'src_idx' in frame:
                        break
                    if 'src' in frame:
                        self.src_idx.append(frame.src)
            self.stack.extend(frames)


#: Global thread-local context.
ctx = Context()


class ContextMixin(object):
    """
    Mixin used to add a convenience `.ctx` property.
    """

    @property
    def ctx(self):
        return ctx
