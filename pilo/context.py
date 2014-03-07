"""
There is a global, thread-local instance of `Context`, `ctx`, used to:

- track source (i.e. parse) and destination (i.e. form) paths in parallel
- and a stack of variables (e.g. `ctx.variables`)

Source and destination paths are managed like:

    .. code:: python
    
        print ctx.src_path, ctx.src_depth
        print ctx.form_path, ctx.form_depth
        with ctx.push('dst', 'src'):
            print ctx.src_path, ctx.src_depth
        print ctx.form_path, ctx.form_depth 

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
        if isinstance(self.func, list):
            for func in self.func:
                func()
        else:
            self.func()


class Context(threading.local):
    """
    Used to manage:
        
    - a stack of variable `Frame`
    - paths with a source and destination (i.e. form).

    You should never need to create this, just use the `ctx` global.
    """

    def __init__(self):
        threading.local.__init__(self)
        self.stack = [Frame(src=None, src_path=None)]
        self.form_path = []

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
        form_path = self.form_path
        self.form_path = []
        self.stack.append(Frame(src=None, src_path=None))
        return Close(functools.partial(self.restore, form_path))

    def restore(self, form_path):
        self.form_path = form_path
        self.stack.pop()

    def push(self, form_key, src_key):
        pops = []
        if form_key:
            pops.append(self.push_form(form_key).func)
        if src_key:
            pops.append(self.push_src(src_key).func)
        return Close(pops)

    def push_form(self, key):
        self.form_path.append(key)
        return Close(self.pop_form)

    def pop_form(self):
        self.form_path.pop()

    @property
    def form_depth(self):
        return len(self.form_path)

    def push_src(self, key):
        if key in (NONE, None):
            return Close(lambda: None)
        if self.src_path is None:
            self.src_path = []
        self.src_path.append(key)
        return Close(self.pop_src)

    def pop_src(self):
        self.src_path.pop()

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
