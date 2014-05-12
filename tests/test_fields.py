import pilo

from . import TestCase


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
