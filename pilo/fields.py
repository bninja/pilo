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
import contextlib
import copy
import datetime
import decimal
import imp
import inspect
import re
import time
import uuid

try:
    import iso8601
except ImportError:
    pass

from . import (
    NONE, NOT_SET, ERROR, IGNORE, ctx, ContextMixin, Close, Source, SourceError, DefaultSource, Types,
)


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
            '{0} - missing'.format(field.ctx.src_path), field,
        )


class Invalid(FieldError):

    def __init__(self, field, violation):
        super(Invalid, self).__init__(
            '{0} - {1}'.format(ctx.src_path, violation), field,
        )
        self.violation = violation


class Errors(object):

    def __call__(self, *ex):
        raise NotImplementedError

    def missing(self):
        self(Missing(ctx.field))

    def invalid(self, violation):
        self(Invalid(ctx.field, violation))


class RaiseErrors(list, Errors):

    def __call__(self, *ex):
        self.extend(ex)
        raise ex[0]


class CollectErrors(list, Errors):

    def __call__(self, *ex):
        self.extend(ex)


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
        target = self.target
        if target is None:
            target = self.parent.ctx.form
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

    def __init__(self,
                 src=NONE,
                 nullable=NONE,
                 default=NOT_SET,
                 optional=False,
                 ignore=None,
                 translate=None
        ):
        super(Field, self).__init__()
        self.compute = Hook(self, inspect.getargspec(self._compute))
        self.resolve = Hook(self, inspect.getargspec(self._resolve))
        self.parse = Hook(self, inspect.getargspec(self._parse))
        self.munge = Hook(self, inspect.getargspec(self._munge))
        self.filter = Hook(self, inspect.getargspec(self._filter))
        self.validate = Hook(self, inspect.getargspec(self._validate))
        self.src = src
        if optional:
            default = NONE
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
        attrs = ', '.join(
            '{0}={1}'.format(k, v) for k, v in [
            ('name', self.name),
            ('src', self.src),
            ('parent', self.parent),
        ])
        return '{0}({1})'.format(type(self).__name__, attrs)

    def attach(self, parent, name=None):
        self.parent, self.name = parent, name
        if self.src is NONE:
            self.src = self.name
        if inspect.isclass(parent) and issubclass(parent, Form):
            for base in inspect.getmro(parent)[1:]:
                if (not hasattr(base, self.name) or
                    not isinstance(getattr(base, self.name), Field)):
                    continue
                self._count = getattr(base, self.name)._count
                break
        return self

    @property
    def is_attached(self):
        return self.parent is not None

    def clone(self):
        other = copy.copy(self)
        other.parent = None
        return other

    def from_context(self):

        def resolve(self):
            return contextlib.nested(
                self.ctx(src=DefaultSource(self.ctx)),
                self.ctx(src=self.src),
            )

        self.resolve.attach(self)(resolve)
        return self

    def constant(self, value):

        def compute(self):
            return value

        if not self.is_attached:
            return self.compute.attach(self)(compute)
        other = self.clone()
        other.compute = Hook(other, inspect.getargspec(other._compute))
        return other.compute.attach(other)(compute)

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
        Processes this fields `src` from `ctx.src`.
        """
        src_path = self.ctx.src_path
        if not src_path.exists:
            return NONE
        if src_path.is_null:
            return None
        try:
            if self.parse:
                value = self.parse(src_path)
            else:
                value = self._parse(src_path)
            return value
        except (SourceError, ValueError), ex:
            self.ctx.errors.invalid(str(ex))
            return ERROR

    def _resolve(self):
        """
        Resolves this fields `src` with `ctx.src`.
        """
        if self.src in (None, NONE):
            return None
        return self.ctx(src=self.src)

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
        if self.default is NOT_SET:
            self.ctx.errors.missing()
        if self.default in IGNORE:
            return self.default
        if isinstance(self.default, type) or callable(self.default):
            return self.default()
        return self.default

    def _map(self, value=NONE):
        # resolve
        close = Close.dummy
        if value is NONE:
            if self.resolve:
                close = self.resolve()
            else:
                close = self._resolve()
            if close is None:
                close = Close.dummy

        with close:
            # compute
            if value is NONE:
                if self.compute:
                    value = self.compute()
                else:
                    value = self._compute()
                if value is NONE:
                    return self._default()
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

    def map(self, value=NONE):
        """
        Executes the steps used to "map" this fields value from `ctx.src` to a
        value.

        :param value: optional **pre-computed** value.

        :return: The successfully mapped value or:

            - NONE if one was not found
            - ERROR if the field was present in `ctx.src` but invalid.

        """
        with self.ctx(field=self, parent=self):
            return self._map(value)

    #: Alias for `map`.
    __call__ = map

    def __get__(self, form, form_type=None):
        if form is None:
            return self
        if not self.compute and self.name in form:
            return form[self.name]
        if getattr(self.ctx, 'form', None) is None:
            with self.ctx(form=form, parent=form, src=DefaultSource({})):
                value = self()
        else:
            if form is not getattr(self.ctx, 'parent', None):
                is_form = lambda frame: getattr(frame, 'parent', None) is form
                try:
                    with self.ctx.rewind(is_form):
                        return self()
                except self.ctx.RewindDidNotStop:
                    with self.ctx(form=form, parent=form, src=DefaultSource({})):
                        value = self()
            else:
                value = self()
        if value in IGNORE:
            raise AttributeError(
                '"{0}" form cannot map field "{1}"'.format(form_type.__name__, self.name),
                self,
            )
        form[self.name] = value
        return value

    def __set__(self, form, value):
        form[self.name] = value

    def __delete__(self, form):
        if form is None:
            return
        if self.name not in form:
            return
        del form[self.name]


class String(Field):

    def __init__(self, *args, **kwargs):
        length = kwargs.pop('length', None)
        if length:
            self.max_length = self.min_length = length
        else:
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

        return self.compute.attach(self)(compute)

    def capture(self, pattern, name=None):
        """
        Hooks munge to capture a value based on a regex.
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

    def _parse(self, path):
        return path.primitive(basestring)

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
                raise ValueError(
                    '{0} does not match pattern "{1}"'.format(
                    value, pattern_re.pattern
                ))
            return int(m.group(0))

        return self.parse(parse)

    def _parse(self, path):
        return path.primitive(int)


Int = Integer


class Float(Number):

    def pattern(self, pattern_re):
        if isinstance(pattern_re, basestring):
            pattern_re = re.compile(pattern_re)

        def parse(self, path):
            value = path.primitive(basestring)
            m = pattern_re.match(value)
            if not m:
                raise ValueError('{0} does not match pattern "{1}"'.format(
                    value, pattern_re.pattern
                ))
            return int(m.group(0))

        return self.parse(parse)

    def _parse(self, path):
        return path.primitive(float)


class Decimal(Number):

    def _parse(self, path):
        if isinstance(path.value, decimal.Decimal):
            return path.value
        if isinstance(path.value, float):
            return decimal.Decimal(path.value)
        value = path.primitive(basestring)
        return decimal.Decimal(value)


class Boolean(Field):

    def _parse(self, path):
        return path.primitive(bool)


Bool = Boolean


class RangeMixin(object):

    def after(self, value):
        self.after_value = value
        return self

    def before(self, value):
        self.before_value = value
        return self

    def between(self, l, r):
        return self.after(l).before(r)


class Date(Field, RangeMixin):

    def __init__(self, *args, **kwargs):
        self.after_value = kwargs.pop('after', None)
        self.before_value = kwargs.pop('before', None)
        self._format = kwargs.pop('format', None)
        super(Date, self).__init__(*args, **kwargs)

    def format(self, value):
        if isinstance(value, datetime.date):
            return value.strftime(self._format)
        self._format = value
        return self

    def _parse(self, path):
        if isinstance(path.value, datetime.date):
            return path.value
        value = path.primitive(basestring)
        if self._format != None:
            parsed = datetime.datetime.strptime(value, self._format).date()
        else:
            ctx.errors.invalid('Unknown format for value "{}"'.format(value))
            return ERROR
        return parsed

    def _validate(self, value):
        if not super(Date, self)._validate(value):
            return False
        if value is not None:
            if self.after_value is not None and value < self.after_value:
                ctx.errors.invalid('Must be after {}'.format(self.after_value))
                return False
            if self.before_value is not None and value > self.before_value:
                ctx.errors.invalid('Must be before {}'.format(self.before_value))
                return False
        return True


class Time(Field, RangeMixin):

    def __init__(self, *args, **kwargs):
        self.after_value = kwargs.pop('after', None)
        self.before_value = kwargs.pop('before', None)
        self._format = kwargs.pop('format', None)
        super(Time, self).__init__(*args, **kwargs)

    def format(self, value):
        if isinstance(value, time.struct_time):
            return time.strftime(self._format, value)
        self._format = value
        return self

    def _parse(self, path):
        value = path.value
        if isinstance(value, (time.struct_time, datetime.time)):
            return value
        value = path.primitive(basestring)
        if self._format != None:
            parsed = time.strptime(value, self._format)
        else:
            ctx.errors.invalid('Unknown format for value "{}"'.format(value))
            return ERROR
        return parsed

    def _validate(self, value):
        if not super(Time, self)._validate(value):
            return False
        if value is not None:
            if self.after_value is not None and value < self.after_value:
                ctx.errors.invalid('Must be after {}'.format(self.after_value))
                return False
            if self.before_value is not None and value > self.before_value:
                ctx.errors.invalid('Must be before {}'.format(self.before_value))
                return False
        return True


class Datetime(Field, RangeMixin):

    def __init__(self, *args, **kwargs):
        self.after_value = kwargs.pop('after', None)
        self.before_value = kwargs.pop('before', None)
        self._format = kwargs.pop('format', None)
        super(Datetime, self).__init__(*args, **kwargs)

    def format(self, value):
        if isinstance(value, datetime.date):
            return value.strftime(self._format)
        self._format = value
        return self

    def _parse(self, path):
        if isinstance(path.value, datetime.datetime):
            return path.value
        value = path.primitive(basestring)
        if self._format == 'iso8601':
            parsed = iso8601.parse_date(value)
        elif self._format != None:
            parsed = datetime.datetime.strptime(value, self._format)
        else:
            ctx.errors.invalid('Unknown format for value "{}"'.format(value))
            return ERROR
        return parsed

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

    def _parse(self, path):
        length = path.sequence()
        if length != len(self.fields):
            ctx.errors.invalid('Must have exactly {0} items'.format(
                len(self.fields)
            ))
            return ERROR
        value = []
        for i in xrange(length):
            with self.ctx(src=i):
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
        self.allow_field = kwargs.pop('allow_field', False)
        super(List, self).__init__(*args, **kwargs)

    def min(self, value):
        self.min_length = value
        return self

    def max(self, value):
        self.max_length = value
        return self

    def range(self, l, r):
        return self.min(l).max(r)

    def _parse(self, path):
        try:
            length = path.sequence()
        except path.src.error:
            if not self.allow_field:
                raise
            value = self.field()
            if value not in IGNORE:
                value = [value]
        else:
            value = []
            for i in xrange(length):
                with self.ctx(src=i):
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
        self.key_filter = Hook(self, inspect.getargspec(self._key_filter))
        self.value_field = value_field.attach(self)
        self.required_keys = kwargs.pop('required_keys', [])
        self.max_keys = kwargs.pop('max_keys', None)
        super(Dict, self).__init__(*args, **kwargs)

    def _key_filter(self, key):
        return True

    def _parse(self, path):
        keys = path.mapping()
        if keys is NONE:
            return self._default()
        mapping = {}
        key_filter = self.key_filter if self.key_filter else self._key_filter
        for key in keys:
            if not key_filter(key):
                continue
            with self.ctx(src=key):
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


class Code(Field):

    pattern = re.compile('(?:(?P<module>[\w\.]+):)?(?P<attr>[\w\.]+)')

    @classmethod
    def inline_match(cls, value):
        return value.count('\n') > 0

    @classmethod
    def import_match(cls, value):
        match = cls.pattern.match(value)
        if not match:
            return False
        return match.group('module'), match.group('attr')

    @classmethod
    def load(cls, name, attr):
        module = __import__(name)
        try:
            obj = reduce(getattr, attr.split('.'), module)
        except AttributeError:
            raise TypeError('Unable to resolve {0}.{1}\n'.format(
                module.__name__, attr
            ))
        return obj

    @classmethod
    def compile(cls, name, code, **code_globals):
        module = imp.new_module('<{0}>'.format(name))
        module.__dict__.update(code_globals)
        exec code in module.__dict__
        return module

    def _parse(self, path):
        value = super(Code, self)._parse(path)
        if value in IGNORE:
            return value

        # in-line
        if self.inline_match(value):
            try:
                return self.compile(self.name, value)
            except Exception, ex:
                self.ctx.errors.invalid(str(ex))
                return ERROR

        # import
        match = self.import_match(value)
        if match:
            name, attr = match
            try:
                return self.load(name, attr)
            except Exception, ex:
                self.ctx.errors.invalid(str(ex))
                return ERROR

        self.ctx.errors.invalid(
            '"{0}" does not match import pattern "{1}" and is not a code block'.format(
            value, self.pattern.pattern
        ))
        return ERROR


class UUID(Field):

    def _parse(self, path):
        value = self.ctx.src_path.primitive()
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(self.ctx.src_path.primitive(basestring))


class Type(String):
    """
    """

    @classmethod
    def abstract(cls):
        return cls()

    @classmethod
    def instance(cls, *choices):
        default = NONE
        if len(choices) == 1:
            default = choices[0]
        return cls(default=default, choices=list(choices))

    def __init__(self, *args, **kwargs):
        self.types = None
        super(Type, self).__init__(*args, **kwargs)

    @property
    def value(self):
        if self.default in IGNORE:
            if not self.choices:
                raise TypeError('{0} is abstract'.format(self))
            raise TypeError('{0} is polymorphic'.format(self))
        return self.default

    def cast(self, value):
        identity = self.probe(value)
        if identity not in self.types:
            raise ValueError('{0} value {1} invalid'.format(self, identity))
        return self.types[identity]

    def probe(self, value):
        if not self.types:
            self.types = Types.map(self)
        return self.types.probe(value)

    def _validate(self, value):
        if not super(Type, self)._validate(value):
            return False
        if self.default is None:
            return True
        return True


class SubForm(Field):

    @classmethod
    def from_fields(cls, **fields):
        return cls(Form.from_fields(**fields))

    def __init__(self, form_type, *args, **kwargs):
        self.form_type = form_type
        self.reset = kwargs.pop('reset', False)
        self.unmapped = kwargs.pop('unmapped', 'ignore')
        super(SubForm, self).__init__(*args, **kwargs)

    def _parse(self, path):
        form = self.form_type()
        errors = form.map(reset=self.reset, unmapped=self.unmapped)
        if errors:
            return ERROR
        return form


class PolymorphicSubForm(Field):

    def __init__(self, type_field, *args, **kwargs):
        self.type_field = type_field
        self.reset = kwargs.pop('reset', False)
        self.unmapped = kwargs.pop('unmapped', 'ignore')
        super(PolymorphicSubForm, self).__init__(*args, **kwargs)

    def _form_type(self, path):
        try:
            identity = self.type_field.probe(path.value)
        except ValueError, ex:
            self.ctx.invalid(str(ex))
            return ERROR
        if identity not in self.type_field.types:
            self.ctx.invalid('invalid identity {}'.format(identity))
            return ERROR
        return self.type_field.types[identity]

    def _parse(self, path):
        form_type = self._form_type(path)
        if form_type in IGNORE:
            return form_type
        form = form_type()
        errors = form.map(reset=self.reset, unmapped=self.unmapped)
        if errors:
            return ERROR
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
            if not attr.is_attached:
                attr.attach(cls, name)
            if attr not in fields:
                fields.append(attr)
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

    @classmethod
    def from_fields(cls, **fields):
        return type('AnonymousForm', (cls,), fields)

    def __init__(self, *args, **kwargs):
        CreatedCountMixin.__init__(self)
        src = None
        if args:
            if isinstance(args[0], Source):
                src = args[0]
                args = args[1:]
            else:
                if isinstance(args[0], (list, tuple)):
                    src = DefaultSource(
                        args[0],
                        aliases=dict(
                            (field.name, i) for i, field in enumerate(self.fields)
                        )
                    )
                else:
                    src = DefaultSource(args[0])
                args = args[1:]
        elif kwargs:
            src = DefaultSource(kwargs)
            kwargs = {}
        dict.__init__(self, *args, **kwargs)
        if src:
            errors = self.map(src)
            if errors:
                raise errors[0]

    def _reset(self, tags):
        for field in type(self).fields:
            if tags and not tags & set(field.tags):
                continue
            try:
                field.__delete__(self)
            except FieldError:
                pass

    def _map(self, tags, unmapped):
        with self.ctx(form=self, parent=self):
            for field in type(self).fields:
                if tags and not tags & set(field.tags):
                    continue
                value = field()
                if value not in IGNORE:
                    self[field.name] = value
        unmapped = self._unmapped(unmapped)
        if unmapped is not None:
            self.update(unmapped)

    def _unmapped(self, directive):
        if not directive:
            return
        if isinstance(directive, basestring):
            if directive == 'capture':
                directive = (String(), Field())
            elif directive == 'ignore':
                return
            else:
                raise ValueError(
                    'unmapped="{}" invalid, should be "capture" or "ignore"'.format(directive)
                )
        if isinstance(directive, Field):
            directive = (String(), directive)

        dict_field = Dict(*directive)
        dict_field.key_filter.attach(self)(lambda self, key: key not in self)
        return dict_field.map()

    def map(self, src=None, tags=None, reset=False, unmapped='ignore', error='collect'):
        tags = tags if tags else getattr(self.ctx, 'tags', None)
        if isinstance(tags, list):
            tags = set(tags)
        if reset:
            self._reset(tags)
        if src is None and self.ctx.src is not None:
            errors = (CollectErrors if error == 'collect' else RaiseErrors)()
            with self.ctx(errors=errors):
                self._map(tags, unmapped)
                errors = self.ctx.errors
            self.ctx.errors.extend(errors)
        else:
            if src is None:
                src = DefaultSource({})
            elif isinstance(src, dict):
                src = DefaultSource(src)
            elif isinstance(src, (list, tuple)):
                src = DefaultSource(
                    src,
                    aliases=dict(
                        (field.name, i) for i, field in enumerate(self.fields)
                    )
                )
            elif isinstance(src, Source):
                pass
            else:
                raise ValueError('Invalid source, expected None, dict or Source')
            errors = (CollectErrors if error == 'collect' else RaiseErrors)()
            with self.ctx(src=src, errors=errors):
                self._map(tags, unmapped)
                errors = self.ctx.errors
        if error == 'collect':
            return errors
        if errors:
            raise errors[0]
        return self

    def munge(self, func):
        form = type(self)()
        for field in type(self).fields:
            value = func(form, field, self.get(field.name, NONE))
            if value is not NONE:
                form[field.name] = value
            if isinstance(value, Form):
                value = value.munge(func)
        return form

    def filter(self, *tags, **kwargs):
        inv = kwargs.get('inv', False)

        def munge(form, field, value):
            hit = any(field.has_tag(tag) for tag in tags)
            if inv:
                hit = not hit
            return value if hit else NONE

        return self.munge(munge)

    def copy(self):
        dst = type(self)()
        for k, v in self.iteritems():
            dst[k] = v
        return dst
