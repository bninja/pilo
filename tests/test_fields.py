import abc
import datetime
import re

import pilo
from pilo.fields import Integer, List, String

from tests import TestCase


class TestForm(TestCase):

    def test_basic(self):

        class MySubForm(pilo.Form):

            sfield1 = pilo.fields.Float(default=12.0)

            sfield2 = pilo.fields.Tuple(
                (pilo.fields.String(), pilo.fields.Integer().min(10)),
                default=None
            )

        class MyForm(pilo.Form):

            field1 = pilo.fields.Int().min(10).max(100)

            @field1.munge
            def field1(self, value):
                return value + 1

            field2 = pilo.fields.Bool('ff2', default=None)

            field3 = pilo.fields.SubForm(MySubForm, 'payload')


        form = MyForm({
            'field1': 55,
            'ff2': 't',
            'payload': {
                'sfield2': ('somestring', '456'),
            }
        })
        self.assertDictEqual(form, {
            'field1': 56,
            'field2': True,
            'field3': {
                'sfield1': 12.0,
                'sfield2': ('somestring', 456),
            }
        })

    def test_form_envelope(self):

        class Form(pilo.Form):

            field1 = pilo.fields.Int().min(10).max(100)

            field2 = pilo.fields.Bool(default=None)

        class Envelope(pilo.Form):

            container = pilo.fields.SubForm(Form, None)

        form = Envelope({
            'field1': 55,
            'field2': True,
        })
        self.assertDictEqual({
            'container': {
                'field1': 55,
                'field2': True,
            }
        }, form)

    def test_field_envelope(self):

        class Envelope(pilo.Form):

            container = pilo.Field(None)

        form = Envelope({
            'field1': 55,
            'field2': True,
        })
        self.assertDictEqual({
            'container': {
                'field1': 55,
                'field2': True,
            }
        }, form)


    def test_rewind(self):

        class MySubForm(pilo.Form):

            link = pilo.fields.String().format('/my/{id}', id='id')

            id = pilo.fields.Integer()


        class MyForm(pilo.Form):

            items = pilo.fields.List(pilo.fields.SubForm(MySubForm))

            checksum = pilo.fields.String()

        form = MyForm({
            'items': [
                {
                    'id': 213123,
                },
                {
                    'id': 567657,
                },
            ],
            'checksum': '123123213',
        })
        self.assertEqual({
            'items': [
                {
                    'link': '/my/213123',
                    'id': 213123,
                },
                {
                    'link': '/my/567657',
                    'id': 567657,
                },
            ],
            'checksum': '123123213',
        }, form)


    def test_clone(self):

        class MySubForm(pilo.Form):

            link = pilo.fields.String().format('/my/{id}', id='id')

            id = pilo.fields.Integer()


        class MyForm(pilo.Form):

            items = pilo.fields.List(pilo.fields.SubForm(MySubForm))

            checksum = pilo.fields.String()

        form = MyForm({
            'items': [
                {
                    'id': 213123,
                },
                {
                    'id': 567657,
                },
            ],
            'checksum': '123123213',
        })
        clone = MyForm(form)
        self.assertEqual({
            'items': [
                {
                    'link': '/my/213123',
                    'id': 213123,
                },
                {
                    'link': '/my/567657',
                    'id': 567657,
                },
            ],
            'checksum': '123123213',
        }, clone)

    def test_unmapped(self):

        class MySubForm(pilo.Form):

            za = pilo.fields.Float()


        class MyForm(pilo.Form):

            z = pilo.fields.SubForm(MySubForm, unmapped='capture')

            a = pilo.fields.String()

            @a.munge
            def a(self, value):
                return value[::-1]

            b = pilo.fields.Integer()

            @b.munge
            def b(self, value):
                return value * 100

        src = {
            'a': 'aeee',
            'b': 1,
            'c': {
                'cc': [1, 2, 3, 4]
            },
            'd': 'blah',
            'e': ['a', 'b', 'c'],
            'f': 123.23,
            'z': {
                'za': 123132.123,
                'zb': '',
                'zc': 12312,
                'zd': {
                    'zba': 12312,
                },
            }
        }

        expected_ignored = {
            'a': 'eeea',
            'b': 100,
            'z': {
                'za': 123132.123,
                'zb': '',
                'zc': 12312,
                'zd': {
                    'zba': 12312,
                },
            }
        }

        expected_captured = {
            'a': 'eeea',
            'b': 100,
            'c': {
                'cc': [1, 2, 3, 4]
            },
            'd': 'blah',
            'e': ['a', 'b', 'c'],
            'f': 123.23,
            'z': {
                'za': 123132.123,
                'zb': '',
                'zc': 12312,
                'zd': {
                    'zba': 12312,
                },
            }
        }

        form = MyForm().map(src, unmapped='ignore', error='raise')
        self.assertEqual(expected_ignored, form)

        form = MyForm().map(src, unmapped='capture', error='raise')
        self.assertEqual(expected_captured, form)

        form = MyForm().map(src, unmapped=pilo.fields.Field(), error='raise')
        self.assertEqual(expected_captured, form)

        form = MyForm().map(
            src,
            unmapped=(pilo.fields.String(), pilo.fields.Field()),
            error='raise',
        )
        self.assertEqual(expected_captured, form)

    def test_group(self):

        src = {
            'a[in]': [1, 2, 3],
            'a[!in]': [123, 34, 133],
            'a.between': (23, 234),
            'b[!=]': 'wings',
            'c[>]': datetime.datetime.utcnow().isoformat(),
        }

        class MyForm(pilo.Form):

            a = pilo.fields.Group(
                ('a', pilo.fields.Integer()),
                (re.compile('^a\[(?P<op>in|\!in)\]$'), pilo.fields.List(pilo.fields.Integer())),
                (re.compile('^a\[(?P<op>\<|\>)]$'), pilo.fields.Integer()),
                (re.compile('^a\.(?P<op>between)$'), pilo.fields.Tuple((pilo.fields.Integer(), pilo.fields.Integer()))),
            )

            b = pilo.fields.Group(
                ('b', pilo.fields.String()),
                (re.compile('^b\[(?P<op>=|\!=)]$'), pilo.fields.String()),
            )

            c = pilo.fields.Group(
                ('c', pilo.fields.Datetime(format='iso8601')),
                (re.compile('^c\[(?P<op>=|\!=\|\<|\>)]$'), pilo.fields.Datetime(format='iso8601')),
            ).options(
                default=lambda: [('c', None, datetime.datetime.utcnow())]
            )

        MyForm(src)


class TestFormPolymorphism(TestCase):

    def test_downcast(self):

        class Animal(pilo.Form):

            kind = pilo.fields.Type.abstract()

        class Cat(Animal):

            kind = pilo.fields.Type.instance('cat')
            sound = pilo.fields.String(default='meow')
            name = pilo.fields.String()

        class Dog(Animal):

            kind = pilo.fields.Type.instance('dog')
            sound = pilo.fields.String(default='woof')
            name = pilo.fields.String()

        cat_dict = dict(name='whiskers', kind='cat')
        dog_dict = dict(name='fido', kind='dog')
        cats = [
            Animal.kind.cast(cat_dict)(**cat_dict),
            Animal.kind.cast(cat_dict)(cat_dict),
        ]
        dogs = [
            Animal.kind.cast(dog_dict)(**dog_dict),
            Animal.kind.cast(dog_dict)(dog_dict),
        ]
        for cat, dog in zip(cats, dogs):
            equalities = [
                (type(cat), Cat),
                (type(dog), Dog),
                (cat.name, cat_dict['name']),
                (dog.name, dog_dict['name']),
                (cat.sound, 'meow'),
                (dog.sound, 'woof'),
            ]
            for left, right in equalities:
                self.assertEqual(left, right)

    def test_computed(self):
        
        class Animal(pilo.Form):

            clothed = pilo.fields.Boolean()

            type = pilo.fields.Type.abstract()

            @type.compute
            def type(self):
                return 'man' if self.clothed else 'beast'
            
            @abc.abstractmethod
            def send_to_zoo(self):
                pass

        class Man(Animal):

            type = pilo.fields.Type.instance('man')

            def send_to_zoo(self):
                raise TypeError('Hey now.')

        class Beast(Animal):

            type = pilo.fields.Type.instance('beast')
            
            def send_to_zoo(self):
                pass

        for desc, cls in [
                (dict(clothed=True), Man),
                (dict(clothed=False), Beast)
            ]:
            obj = Animal.type.cast(desc)(desc)
            self.assertIsInstance(obj, cls)

    def test_exceptions(self):

        class Image(pilo.Field):

            supported_encodings = ['base64']
            supported_formats = ['png']

            def __init__(self, *args, **kwargs):
                self.encoding = kwargs.pop('encoding', None)
                self.format = kwargs.pop('format', None)
                super(Image, self).__init__(*args, **kwargs)

            def _parse(self, path):
                return path.value.decode(self.encoding)

            def _validate(self, value):
                predicate_by_format = dict(
                    png=lambda value: value[:8] == '\211PNG\r\n\032\n'
                )
                predicate = predicate_by_format.get(self.format)
                if predicate and predicate(value):
                    return True
                self.ctx.errors.invalid(
                    'Image must be formatted as {0}'.format(self.format)
                )
                return False

        class DatingProfile(pilo.Form):

            genders = ['male', 'female', 'neutral']

            name = String()
            email = String()
            postal_code = String(length=5)
            blurb = String(max_length=100)
            gender = String(choices=genders)
            sexual_preferences = List(String(choices=genders))
            likes = List(String())
            picture = Image(format='png', encoding='base64')

        profile_params_with_one_error = dict(
            name='William Henry Cavendish III',
            email='whc@example.org',
            postal_code='9021',  # Invalid length
            blurb='I am a test fixture',
            gender='male',
            sexual_preferences=['female', 'neutral'],
            likes=['croquet', 'muesli', 'ruses', 'umbrellas', 'wenches'],
            picture='iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAA1UlEQ'
                    'VRYR+1XQRKAIAjUr/SbXtxv\n+kqNBxsjcCFsGmfoqsC6C5vmlNKRf'
                    'vxyAEAMHPvqEigvWzeelaAtihIgdCjXA0AJ8BaVQHG5bwC+\nLF5B0'
                    'RoXAG3x3r43OQLAjYGiE2pArwR1KmodcxOOANAeMgCYGUDOh9ZFHy'
                    'iBtEFQMus6l19txVqT\nqQfhpglasTXY4vlS7rkY0BqVtM8lQdukXA'
                    'H033dLQPWmNyVk4cMBWEdwLgCaZrMyIJlc91JKddXe\nkKU4rk+6D5'
                    'M3jUanBbEZL6Ng4HcGTmCz+wGYWb2FAAAAAElFTkSuQmCC\n'
        )
        profile_params_with_two_errors = dict(
            name='William Henry Cavendish III',
            email='whc@example.org',
            postal_code='9021',  # Invalid length
            blurb='I am a test fixture',
            gender='male',
            sexual_preferences=['female', 'neutral'],
            likes=['croquet', 'muesli', 'ruses', 'umbrellas', 'wenches'],
            picture='PHN2ZyBoZWlnaHQ9IjEwMCIgd2lkdGg9IjEwMCI+CiAgPGNpcmNsZ'
                    'SBjeD0iNTAiIGN5PSI1MCIg\ncj0iNDAiIHN0cm9rZT0iYmxhY2siI'
                    'HN0cm9rZS13aWR0aD0iMyIgZmlsbD0icmVkIiAvPgogIFNv\ncnJ5L'
                    'CB5b3VyIGJyb3dzZXIgZG9lcyBub3Qgc3VwcG9ydCBpbmxpbmUgU1'
                    'ZHLiAgCjwvc3ZnPiA=\n'  # SVG Image
        )
        profile_params_with_three_errors = dict(
            name='William Henry Cavendish III',
            email='whc@example.org',
            postal_code='9021',  # Invalid length
            blurb='I am a test fixture',
            gender='male',
            sexual_preferences=['aliens'],
            likes=['croquet', 'muesli', 'ruses', 'umbrellas', 'wenches'],
            # No picture
        )
        with self.assertRaises(pilo.fields.Invalid):
            DatingProfile(**profile_params_with_one_error)

        with self.assertRaises(pilo.fields.FieldError):
            DatingProfile(**profile_params_with_two_errors)

        with self.assertRaises(pilo.fields.Invalid):
            DatingProfile(**profile_params_with_two_errors)

        with self.assertRaises(pilo.fields.MultipleExceptions):
            DatingProfile(**profile_params_with_two_errors)

        with self.assertRaises(pilo.fields.MultipleExceptions):
            DatingProfile(**profile_params_with_three_errors)

        with self.assertRaises(pilo.fields.Invalid):
            DatingProfile(**profile_params_with_three_errors)

        with self.assertRaises(pilo.fields.Missing):
            DatingProfile(**profile_params_with_three_errors)

        with self.assertRaises(pilo.fields.FieldError):
            DatingProfile(**profile_params_with_three_errors)
