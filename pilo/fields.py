"""
This defines `Form` and the `Field`s use to build them. Use it like:

    .. code:: python

        import pilo
        import pprint

        class MySubForm(pilo.Form):

            sfield1 = pilo.fields.Float(default=12.0)

            sfield2 = pilo.fields.Tuple(
                pilo.fields.String(), pilo.fields.Integer().min(10),
                default=None
            )


        class MyForm(pilo.Form)

            field1 = pilo.fields.Integer().min(10).max(100)

            @field1.munge
            def field1(self, value):
                return value + 1

            field2 = pilo.Bool('ff2', default=None)

            field3 = pilo.fields.SubForm(MySubForm, 'payload')


        form = MyForm({
            'field1': 55,
            'ff2': True,
            'payload': {
                'sfield2': ('somestring', 456),
            }
        })

        pprint.pprint(form)
        print form.payload.sfield

"""
from datetime import datetime
import decimal
import inspect
import re

from . import NONE, ERROR, IGNORE, ctx, ContextMixin, Source, DefaultSource
from IPython.testing.plugin.dtexample import ipfunc


__all__ = [
    'Field'
    'String',
    'Integer',
    'Int',
    'Float',
    'Decimal',
    'Boolean',
    'Bool',
    'List'
    'Dict'
    'SubForm',
    'Form',
]


class FieldError(ValueError):

    def __init__(self, message, field):
        super(FieldError, self).__init__(message)
        self.field = field
        self.path = field.ctx.src_path


class Missing(FieldError):

    def __init__(self, field):
        super(Missing, self).__init__(
            '{0}'.format(field.ctx.src_path), field,
        )


class Invalid(FieldError):

    def __init__(self, field, violation):
        super(Invalid, self).__init__(
            '{0} - {1}'.format(ctx.src_path, violation), field,
        )
        self.violation = violation


class Errors(list):

    def missing(self):
        self.append(Missing(ctx.field))

    def invalid(self, violation):
        self.append(Invalid(ctx.field, violation))


class CreatedCountMixin(object):
    """
    Mixin used to add a `._count` instance value that can use used to sort
    instances in creation order.
    """

    _created_count = 0

    def  __init__(self):
        CreatedCountMixin._created_count += 1
        self._count = CreatedCountMixin._created_count


class Hook(object):
    """
    An override-able hook allowing users to inject functions to customize
    behavior. By using this we allow stuff like:


    .. code:: python

        class Form(pilo.Form)

            f1 = pilo.fields.Integer(default=None)

            @f1.filter
            def field1(self, value):
                return value < 10

    """

    def __init__(self, parent, func_spec):
        self.parent = parent
        self.target = None
        self.func = None
        self.func_spec = func_spec

    def attach(self, target):
        self.target = target
        return self

    def __bool__(self):
        return self.func is not None

    __nonzero__ = __bool__

    def __call__(self, *args, **kwargs):
        # register
        if self.func is None and args and callable(args[0]):
            func = args[0]
            if inspect.getargspec(func) != self.func_spec:
                raise TypeError('{0} signature does not match {1}'.format(
                    func.__name__, self.func_spec
                ))
            self.func = func
            parent = self.parent
            while isinstance(parent, Field) and parent.parent:
                parent = parent.parent
            return parent

        # invoke
        target = self.target or self.parent.ctx.form
        return self.func(target, *args, **kwargs)


class Field(CreatedCountMixin, ContextMixin):
    """
    A field is used to "map" a value from a source to named value. As part of
    that mapping processes is done in Field.__call__ as is made up of these
    steps:

        - compute (see `Field._compute`)
            - resolve (see `Field._resolve`)
            - parse (see `Field._parse`)
        - munge  (see `Field._munge`)
        - filter  (see `Field._filter`)
        - validate  (see `Field._validate`)

    You can hook any of these steps using the corresponding hook, so e.g.:

    .. code:: python

        class MyForm(pilo.Form)

            factor = pilo.fields.Integer()

            @factor.munge
            def factor(self value):
                return math.radian(value)

    Here are the important attributes:

    `name`
        The name of this field as a string. This will typically be whatever
        name is assigned a field when its attached to a `Form`:

        .. code:: python

            class Form(pilo.Form)

                hiya = pilo.fields.Bool()

        Here field Form.hyia.name is "hyia".

    `src`
        This is the key of this field in a `Source`. This will default to
        `name` but you can override it:

        .. code:: python

            class Form(pilo.Form)

                hiya = pilo.fields.Bool()

                bye = pilo.fields.Bool('adieu')

        Here field Form.hyia.src is "hyia" but Form.bye.src is "adieu".

    `default`
        This is the default value of this field to use if `src` is not present
        in `Source`.

    `nullable`
        Flag indicating whether or not this field's value can be None. Note
        that if `default` is None then `nullable` will be True

    `ignores`
        A list of literal values to ignore. If a value it ignored `default`
        will be used. If you have more complicated **filtering** logic use a
        `Field.filter` hook.

    `translations`
        A mapping use to translated field values to other literal values. e.g.

        .. code:: python

            class Form(pilo.Form)

                hiya = pilo.fields.String(choices=['one', 'two']).translate({'one': 1, 'two': 2})

        If you have more complicated **munging** logic use a `Field.munge` hook.

    `parent`
        This is the immediate parent this field is attached to. It will
        typically be a `Form` but can be another `Field`:

        .. code:: python

            class MyForm(pilo.Form)

                hiya = pilo.fields.Bool()

                peeps = pilo.fields.List(pilo.fields.String())

        Here MyForm.hiya.parent is MyForm while Form.peeps.field.parent is
        MyForm.peeps.

    `tags`
        A list of strings to tag this field with.

    """

    def __init__(self, src=NONE, nullable=NONE, default=NONE, ignore=None, translate=None):
        super(Field, self).__init__()
        self.compute = Hook(self, inspect.getargspec(self._compute))
        self.resolve = Hook(self, inspect.getargspec(self._resolve))
        self.parse = Hook(self, inspect.getargspec(self._parse))
        self.munge = Hook(self, inspect.getargspec(self._munge))
        self.filter = Hook(self, inspect.getargspec(self._filter))
        self.validate = Hook(self, inspect.getargspec(self._validate))
        self.src = src
        self.default = default
        if nullable is NONE and self.default is None:
            self.nullable = True
        else:
            self.nullable = nullable
        self.ignores = ignore or []
        self.translations = translate or {}
        self.parent = None
        self.name = None
        self.tags = []

    def __str__(self):
        return '{}(name="{}")'.format(type(self).__name__, self.name)

    def attach(self, parent, name=None):
        self.parent, self.name = parent, name
        if self.src is NONE:
            self.src = self.name
        return self

    def is_attached(self):
        return self.parent is not None

    def from_context(self):

        def compute(self):
            try:
                return reduce(getattr, self.src.split('.'), self.ctx)
            except AttributeError, ex:
                self.ctx.errors.invalid(str(ex))
                return ERROR

        self.compute.attach(self)(compute)
        return self

    def constant(self, value):

        def compute(self):
            return value

        return self.compute(compute)

    def ignore(self, *args):
        self.ignores.extend(args)
        return self

    def translate(self, kwargs):
        self.translations.update(kwargs)
        return self

    def has_tag(self, tag):
        return tag in self.tags

    def tag(self, *tags):
        self.tags.extend(tags)
        return self

    def _compute(self):
        """
        Resolves and parses this fields `src` from `ctx.src`.
        """
        if self.resolve:
            path = self.resolve()
        else:
            path = self._resolve()
        if path is None:
            return path
        if path is NONE:
            return self._default()
        try:
            if self.parse:
                value = self.parse(path)
            else:
                value = self._parse(path)
            return value
        except ValueError, ex:
            self.ctx.errors.invalid(str(ex))
            return ERROR

    def _resolve(self):
        """
        Resolves this fields `src` with `ctx.src`. The return value is passed
        to `_parse`.
        """
        if not self.ctx.src_path.exists:
            return NONE
        return self.ctx.src_path

    def _parse(self, path):
        """
        Parses a `src` path. The return value is typically passed along to to
        `_munge`.
        """
        return path.primitive(None)

    def _filter(self, value):
        """
        Predicate used to exclude, False, or include, True, a computed value.
        """
        if self.ignores and value in self.ignores:
            return False
        return True

    def _validate(self, value):
        """
        Predicate used to determine if a computed value is valid, True, or
        not, False.
        """
        if value is None and not self.nullable:
            ctx.errors.invalid('not nullable')
            return False
        return True

    def _munge(self, value):
        """
        Possibly munges a value.
        """
        if self.translations and value in self.translations:
            value = self.translations[value]
        return value

    def _default(self):
        if self.default is NONE:
            self.ctx.errors.missing()
            return ERROR
        if isinstance(self.default, type):
            return self.default()
        return self.default

    def __call__(self, value=NONE):
        """
        Executes the steps used to "map" this fields value from `ctx.src` to a
        value.

        :param value: optional **pre-computed** value.

        :return: The successfully mapped value or:

            - MISSING if none was not found
            - ERROR if the field was present in `ctx.src` but invalid.

        """
        with self.ctx(field=self):
            if not hasattr(self.ctx, 'src_path'):
                return self._default()
            try:
                if self.src not in (NONE, None):
                    self.ctx.src_path.push(self.src)

                if value is NONE:
                    # compute
                    if self.compute:
                        value = self.compute()
                    else:
                        value = self._compute()
                    if value in IGNORE:
                        return value

                # munge
                value = self._munge(value)
                if value not in IGNORE and self.munge:
                    value = self.munge(value)
                if value is NONE:
                    return self._default()
                if value in IGNORE:
                    return value

                # filter
                if not self._filter(value) or (self.filter and not self.filter(value)):
                    return self._default()

                # validate
                if not self._validate(value) or (self.validate and not self.validate(value)):
                    return ERROR
                return value
            finally:
                if self.src not in (NONE, None):
                    self.ctx.src_path.pop()

    def __get__(self, form, form_type=None):
        if form is None:
            return self
        if self.name in form:
            return form[self.name]
        value = self()
        if value in IGNORE:
            raise FieldError(
                '"{0}" form cannot map field "{1}"'.format(form_type.__name__, self.name),
                self,
            )
        form[self.name] = value
        return value

    def __set__(self, form, value):
        form[self.name] = value


class String(Field):

    def __init__(self, *args, **kwargs):
        self.min_length = kwargs.pop('min_length', None)
        self.max_length = kwargs.pop('max_length', None)
        pattern = kwargs.pop('pattern', None)
        if pattern:
            if isinstance(pattern, basestring):
                pattern = re.compile(pattern)
            self.pattern_re = pattern
        else:
            self.pattern_re = None
        self.choices = kwargs.pop('choices', None)
        super(String, self).__init__(*args, **kwargs)

    def format(self, fmt, **kwargs):
        """
        Hooks compute to generate a value from a format string.
        """

        def compute(self):
            values = {}
            try:
                for name, field in kwargs.iteritems():
                    values[name] = reduce(getattr, field.split('.'), self.ctx.form)
            except AttributeError, ex:
                self.ctx.errors.invalid(str(ex))
                return ERROR
            return fmt.format(**values)

        return self.compute(compute)

    def capture(self, pattern, name=None):
        """
        Hooks munge to capture a value based in a regex pattern.
        """

        if isinstance(pattern, basestring):
            pattern = re.compile(pattern)

        def munge(self, value):
            match = pattern.match(value)
            if not match:
                return NONE
            for group in [name or self.name, 1]:
                try:
                    return match.group(group)
                except IndexError:
                    pass
            return NONE

        return self.munge.attach(self)(munge)

    def _parse(self, value):
        return self.ctx.src_path.primitive(basestring)

    def _validate(self, value):
        if not super(String, self)._validate(value):
            return False
        if value is None:
            return True
        if (self.min_length is not None and len(value) < self.min_length):
            self.ctx.errors.invalid('"{}" must have length >= {}'.format(
                value, self.min_length
            ))
            return False
        if (self.max_length is not None and len(value) > self.max_length):
            self.ctx.errors.invalid('"{}" must have length <= {}'.format(
                value, self.max_length
            ))
            return False
        if self.pattern_re and not self.pattern_re.match(value):
            self.ctx.errors.invalid('"{}" must match pattern "{}"'.format(
                value, self.pattern_re.pattern
            ))
            return False
        if self.choices and value not in self.choices + self.translations.values():
            if len(self.choices) == 1:
                self.ctx.errors.invalid('"{}" is not "{}"'.format(
                    value, self.choices[0],
                ))
            else:
                self.ctx.errors.invalid('"{}" is not one of {}'.format(
                    value, ', '.join(['"{}"'.format(c) for c in self.choices]),
                ))
            return False
        return True


class Number(Field):

    def __init__(self, *args, **kwargs):
        self.min_value = kwargs.pop('min_value', None)
        self.max_value = kwargs.pop('max_value', None)
        super(Number, self).__init__(*args, **kwargs)

    def min(self, value):
        self.min_value = value
        return self

    def max(self, value):
        self.max_value = value
        return self

    def range(self, l, r):
        return self.min(l).max(r)

    def _validate(self, value):
        if not super(Number, self)._validate(value):
            return False
        if value is not None:
            if self.min_value is not None and value < self.min_value:
                ctx.errors.invalid('"{}" must be >= {}'.format(
                    value, self.min_value
                ))
                return False
            if self.max_value is not None and value > self.max_value:
                ctx.errors.invalid('"{}" must be <= {}'.format(
                    value, self.max_value
                ))
                return False
        return True


class Integer(Number):

    def pattern(self, pattern_re):
        if isinstance(pattern_re, basestring):
            pattern_re = re.compile(pattern_re)

        def parse(self, path):
            value = path.primitive(basestring)
            m = pattern_re.match(value)
            if not m:
                raise ValueError('{} does not match pattern "{}"'.format(
                    value, pattern_re.pattern
                ))
            return int(m.group(0))

        return self.parse(parse)

    def _parse(self, path):
        return ctx.src_path.primitive(int)


Int = Integer


class Float(Number):

    def pattern(self, pattern_re):
        if isinstance(pattern_re, basestring):
            pattern_re = re.compile(pattern_re)

        def parse(self, path):
            value = path.primitive(basestring)
            m = pattern_re.match(value)
            if not m:
                raise ValueError('{} does not match pattern "{}"'.format(
                    value, pattern_re.pattern
                ))
            return int(m.group(0))

        return self.parse(parse)

    def _parse(self, path):
        return path.primitive(float)


class Decimal(Number):

    def _parse(self, path):
        return path.primitive(decimal.Decimal)



class Boolean(Field):

    def _parse(self, path):
        return path.primitive(bool)


Bool = Boolean


class Datetime(Field):

    def __init__(self, *args, **kwargs):
        self.after_value = kwargs.pop('after', None)
        self.before_value = kwargs.pop('before', None)
        self.strptime_fmt = kwargs.pop('format')
        super(Datetime, self).__init__(*args, **kwargs)

    def after(self, value):
        self.after_value = value
        return self

    def before(self, value):
        self.before_value = value
        return self

    def between(self, l, r):
        return self.after(l).before(r)

    def format(self, fmt):
        self.strptime_fmt = fmt
        return self

    def _parse(self, path):
        value = path.primitive(basestring)
        return datetime.strptime(value, self.strptime_fmt)

    def _validate(self, value):
        if not super(Datetime, self)._validate(value):
            return False
        if value is not None:
            if self.after_value is not None and value < self.after_value:
                ctx.errors.invalid('Must be after {}'.format(self.after_value))
                return False
            if self.before_value is not None and value > self.before_value:
                ctx.errors.invalid('Must be before {}'.format(self.before_value))
                return False
        return True


class Tuple(Field):

    def __init__(self, fields, *args, **kwargs):
        if not isinstance(fields, (tuple, list)):
            raise ValueError(
               'Invalid fields "{0}" should be a sequence of {1} instances'
               .format(fields, Field.__name__)
            )
        self.fields = fields
        super(Tuple, self).__init__(*args, **kwargs)

    def _compute(self):
        if not self.ctx.src_path.exists:
            return self._default()
        if self.ctx.src_path.is_null:
            return None
        length = self.ctx.src_path.sequence()
        if length != len(self.fields):
            ctx.errors.invalid('Must have exactly {0} items'.format(
                len(self.fields)
            ))
            return ERROR
        value = []
        for i in xrange(length):
            with self.ctx.src_path.push(i):
                item = self.fields[i]()
                if item in IGNORE:
                    continue
                value.append(item)
        return tuple(value)


class List(Field):

    def __init__(self, field, *args, **kwargs):
        self.field = field.attach(self, None)
        self.min_length = kwargs.pop('min_length', None)
        self.max_length = kwargs.pop('max_length', None)
        super(List, self).__init__(*args, **kwargs)

    def min(self, value):
        self.min_length = value
        return self

    def max(self, value):
        self.max_length = value
        return self

    def range(self, l, r):
        return self.min(l).max(r)

    def _compute(self):
        if not self.ctx.src_path.exists:
            return self._default()
        length = self.ctx.src_path.sequence()
        if length is NONE:
            return self._default()
        value = []
        for i in xrange(length):
            with self.ctx.src_path.push(i):
                item = self.field()
                if item in IGNORE:
                    continue
                value.append(item)
        return value

    def _validate(self, value):
        if not super(List, self)._validate(value):
            return False
        if value is not None:
            if self.min_length is not None and len(value) < self.min_length:
                ctx.errors.invalid('Must have {} or more items'.format(
                    self.min_length
                ))
                return False
            if self.max_length is not None and len(value) > self.max_length:
                ctx.errors.invalid('Must have {} or fewer items'.format(
                    self.max_length
                ))
                return False
        return True


class Dict(Field):

    def __init__(self, key_field, value_field, *args, **kwargs):
        self.key_field = key_field.attach(self)
        self.value_field = value_field.attach(self)
        self.required_keys = kwargs.pop('required_keys', [])
        self.max_keys = kwargs.pop('max_keys', None)
        super(Dict, self).__init__(*args, **kwargs)

    def _compute(self):
        if not self.ctx.src_path.exists:
            return self._default()
        if self.ctx.src_path.is_null:
            return None
        keys = self.ctx.src_path.mapping()
        if keys is NONE:
            return self._default()
        mapping = {}
        for key in keys:
            with self.ctx.src_path.push(key):
                value = self.value_field()
                if value in IGNORE:
                    continue
                key = self.key_field(key)
                if key in IGNORE:
                    continue
                mapping[key] = value
        return mapping

    def _validate(self, value):
        if not super(Dict, self)._validate(value):
            return False
        if value is not None:
            if self.required_keys:
                missing_keys = self.required_keys.difference(value.keys())
                if missing_keys:
                    self.ctx.errors.invalid('Missing required keys {}'.format(
                        ', '.join(missing_keys)
                    ))
                    return False
            if self.max_keys and len(value) > self.max_keys:
                self.ctx.errors.invalid('Cannot have more than {} key(s)'.format(
                    self.max_keys
                ))
                return False
        return True


class SubForm(Field):

    def __init__(self, form_type, *args, **kwargs):
        self.form_type = form_type
        super(SubForm, self).__init__(*args, **kwargs)

    def _compute(self):
        form = self.form_type()
        form()
        return form


class FormMeta(type):
    """
    Used to auto-magically register a `Form`s fields:

    .. code:: python

        class MyForm(pilo.Form)

            a_int = pilo.field.Integer()

    Now:

        - MyForm.a_int.attach(MyForm, 'a_int') has been called and
        - MyForm.fields is [MyForm.a_int]

    """

    def __new__(mcs, name, bases, dikt):
        cls = type.__new__(mcs, name, bases, dikt)
        is_field = lambda x: isinstance(x, Field)
        fields = []
        for name, attr in inspect.getmembers(cls, is_field):
            attr.attach(cls, name)
            fields.append(attr)
            continue
        fields.sort(key=lambda x: x._count)
        cls.fields = fields
        return cls


class Form(dict, CreatedCountMixin, ContextMixin):
    """
    This is a `dict` with an associated list of attached fields and typically
    represents some mapping structured to be parsed out of a `Source`.

    To use it you will typically declare one like:

    .. code:: python

        class MyForm(pilo.Form)

            field1 = pilo.fields.Integer().min(10).max(100).tag('buggy')

            @field1.munge
            def field1(self, value):
                return value + 1

            field2 = pilo.Bool('ff2', default=None)

    and then parse it like:

    .. code:: python

        form = MyForm({
            'field1': 55,
            'ff2': True,
            'payload': {
                'sfield2': ('somestring', 456),
            }
        })

    Here we are just using a plain old `dict` as the `Source` (i.e. the
    `source.DefaultSource`). Note that you can also call a form to process a source:

    .. code:: python

        form = MyForm()
        form.({
            'field1': 55,
            'ff2': True,
            'payload': {
                'sfield2': ('somestring', 456),
            }
        })

    """

    __metaclass__ = FormMeta

    fields = None

    def __init__(self, *args, **kwargs):
        CreatedCountMixin.__init__(self)
        src = None
        if args:
            if isinstance(args[0], Source):
                src = args[0]
                args = args[1:]
            elif isinstance(args[0], dict):
                src = DefaultSource(args[0])
                args = args[1:]
        elif kwargs:
            src = DefaultSource(kwargs)
            kwargs = {}
        dict.__init__(self, *args, **kwargs)
        if src:
            errors = self(src)
            if errors:
                raise errors[0]

    def __call__(self, src=None, tags=None):
        tags = tags if tags else getattr(self.ctx, 'tags', None)
        if isinstance(tags, list):
            tags = set(tags)
        with self.ctx(form=self):
            if src is None and self.ctx.src is not None:
                for field in type(self).fields:
                    try:
                        field.__get__(self, type(self))
                    except FieldError:
                        pass
                return self

            if src is None:
                src = DefaultSource({})
            elif isinstance(src, dict):
                src = DefaultSource(src)
            elif isinstance(src, Source):
                pass
            else:
                raise ValueError('Invalid source, expected None, dict or Source')
            with self.ctx(src=src, src_path=src.path(), errors=Errors()):
                for field in type(self).fields:
                    if tags and not tags & set(field.tags):
                        continue
                    try:
                        field.__get__(self, type(self))
                    except FieldError:
                        pass
                return self.ctx.errors

    def filter(self, *tags, **kwargs):
        inv = kwargs.get('inv', False)
        form = type(self)()
        for field in type(self).fields:
            if field.name not in self:
                continue
            if inv:
                if any(field.has_tag(tag) for tag in tags):
                    continue
            else:
                if not any(field.has_tag(tag) for tag in tags):
                    continue
            value = self[field.name]
            if isinstance(value, Form):
                value = value.filter(*tags, **kwargs)
            form[field.name] = value
        return form
