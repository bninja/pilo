import abc
import datetime
import re

import pilo
from pilo.fields import Integer, List, String, SubForm

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
                (re.compile(r'^a\[(?P<op>in|\!in)\]$'), pilo.fields.List(pilo.fields.Integer())),
                (re.compile(r'^a\[(?P<op>\<|\>)]$'), pilo.fields.Integer()),
                (
                    re.compile(r'^a\.(?P<op>between)$'),
                    pilo.fields.Tuple((pilo.fields.Integer(), pilo.fields.Integer()))
                ),
            )

            b = pilo.fields.Group(
                ('b', pilo.fields.String()),
                (re.compile(r'^b\[(?P<op>=|\!=)]$'), pilo.fields.String()),
            )

            c = pilo.fields.Group(
                ('c', pilo.fields.Datetime(format='iso8601')),
                (re.compile(r'^c\[(?P<op>=|\!=\|\<|\>)]$'), pilo.fields.Datetime(format='iso8601')),
            ).options(
                default=lambda: [('c', None, datetime.datetime.utcnow())]
            )

        MyForm(src)

    def test_decimal_integer(self):
        class MyForm(pilo.Form):
            amt = pilo.fields.Decimal()

        try:
            MyForm(dict(amt=0))
        except pilo.fields.Invalid:
            self.fail("Failed to parse integer decimal value")


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

        for desc, cls in [(dict(clothed=True), Man), (dict(clothed=False), Beast)]:
            obj = Animal.type.cast(desc)(desc)
            self.assertIsInstance(obj, cls)


class TestFormExceptions(TestCase):

    def test_exceptions(self):

        class DatingProfile(pilo.Form):

            genders = ['male', 'female', 'neutral']

            name = String()
            email = String()
            postal_code = String(length=5)
            blurb = String(max_length=100)
            gender = String(choices=genders)
            preferences = List(String(choices=genders))
            likes = List(String())

        profile_with_one_error = dict(
            name='William Henry Cavendish III',
            email='whc@example.org',
            postal_code='9021',  # Invalid length
            blurb='I am a test fixture',
            gender='male',
            preferences=['female', 'neutral'],
            likes=['croquet', 'muesli', 'ruses', 'umbrellas', 'wenches'],
        )
        profile_with_two_errors = dict(
            name='William Henry Cavendish III',
            email='whc@example.org',
            postal_code='9021',  # Invalid postal code
            blurb='I am a test fixture',
            gender='male',
            preferences=['female', 'neutral'],
            # Likes parameter missing
        )
        profile_with_three_errors = dict(
            name='William Henry Cavendish III',
            email='whc@example.org',
            postal_code='9021',  # Invalid length
            blurb='I am a test fixture',
            gender='male',
            preferences=['alien'],  # Invalid preference
            # likes is missing
        )

        with self.assertRaises(pilo.fields.FormError) as ctx:
            DatingProfile(profile_with_one_error)

        self.assertEquals(
            ctx.exception.message,
            '\n'
            '* Invalid: postal_code - "9021" must have length >= 5'
            '\n'
        )
        with self.assertRaises(pilo.fields.FormError) as ctx:
            DatingProfile(profile_with_two_errors)

        self.assertEquals(
            ctx.exception.message,
            '\n'
            '* Invalid: postal_code - "9021" must have length >= 5'
            '\n'
            '* Missing: likes - missing'
            '\n'
        )
        with self.assertRaises(pilo.fields.FormError) as ctx:
            DatingProfile(profile_with_three_errors)

        self.assertEquals(
            ctx.exception.message,
            '\n'
            '* Invalid: postal_code - "9021" must have length >= 5'
            '\n'
            '* Invalid: preferences[0] - "alien" is not one of "male", '
            '"female", "neutral"'
            '\n'
            '* Missing: likes - missing'
            '\n'
        )

    def test_exceptions_in_nested_forms(self):

        class DatingProfile(pilo.Form):

            genders = ['male', 'female', 'neutral']

            name = String()
            email = String()
            postal_code = String(length=5)
            blurb = String(max_length=100)
            gender = String(choices=genders)
            preferences = List(String(choices=genders))
            likes = List(String())

        class Matches(pilo.Form):

            similarity = Integer()
            candidates = List(SubForm(DatingProfile))

        with self.assertRaises(pilo.fields.FormError) as ctx:
            Matches(
                similarity="Not an integer",
                candidates=[
                    dict(
                        name='William Henry Cavendish III',
                        email='whc@example.org',
                        postal_code='9021',  # Invalid postal code
                        blurb='I am a test fixture',
                        gender='male',
                        preferences=['female', 'neutral'],
                        # Likes parameter missing
                    ),
                    dict(),
                    ]
            )
        self.assertEquals(
            ctx.exception.message,
            '\n'
            '* Invalid: similarity - "Not an integer" is not an integer'
            '\n'
            '* Invalid: candidates[0].postal_code - "9021" must have length >= 5'
            '\n'
            '* Missing: candidates[0].likes - missing'
            '\n'
            '* Missing: candidates[1].name - missing'
            '\n'
            '* Missing: candidates[1].email - missing'
            '\n'
            '* Missing: candidates[1].postal_code - missing'
            '\n'
            '* Missing: candidates[1].blurb - missing'
            '\n'
            '* Missing: candidates[1].gender - missing'
            '\n'
            '* Missing: candidates[1].preferences - missing'
            '\n'
            '* Missing: candidates[1].likes - missing'
            '\n'
        )
