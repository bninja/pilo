import abc
import datetime
import re

import pilo

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

    def test_override_hook(self):
        """
        Test that Sub-classes can independently provide hooks on the fields by
        cloning.
        """

        class Item(pilo.Form):
            price = pilo.fields.Integer()

        class Heirloom(Item):

            has_sentimental_value = pilo.fields.Boolean()

            price = Item.price.clone()

            @price.compute
            def get_price(self):
                return 1000000 if self.has_sentimental_value else 0

        item = Item(price=100)
        self.assertEqual(item.price, 100)

        heirloom = Heirloom(has_sentimental_value=False)
        self.assertEqual(heirloom.price, 0)
