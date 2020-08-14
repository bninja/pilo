from __future__ import with_statement

import json
import six

import pilo

from . import TestCase


class TestSource(TestCase):

    def result(self):
        return (
            str(pilo.ctx.src_path),
            pilo.ctx.src_path.exists,
            pilo.ctx.src_path.is_null,
        )


class TestDefaultSource(TestSource):

    def test_path(self):
        src = pilo.source.DefaultSource({
            'slurp': {
                'state_dir': '/var/lib/slurp',
                'backfill': 'f',
                'strict': 'F',
                'read_size': '1024',
                'buffer_size': '1048576',
                'poop': None,
                'includes': ['/etc/slurp/conf.d/*.conf', '/etc/slurp/conf.d/*.py'],
                }})

        results = []

        with pilo.ctx.push(src=src):
            results.append(self.result())
            with pilo.ctx.push(src='slurp'):
                results.append(self.result())
                with pilo.ctx.push(src='includes'):
                    results.append(self.result())
                    with pilo.ctx.push(src=0):
                        results.append(self.result())
                    with pilo.ctx.push(src=1):
                        results.append(self.result())
                    with pilo.ctx.push(src=2):
                        results.append(self.result())
                    with pilo.ctx.push(src='peep'):
                        results.append(self.result())
                    results.append(self.result())
                with pilo.ctx.push(src=2):
                    results.append(self.result())
                with pilo.ctx.push(src='backfill'):
                    results.append(self.result())
                with pilo.ctx.push(src='read_size'):
                    results.append(self.result())

        self.maxDiff = None
        self.assertEqual([
            ('', True, False),
            ('slurp', True, False),
            ('slurp.includes', True, False),
            ('slurp.includes[0]', True, False),
            ('slurp.includes[1]', True, False),
            ('slurp.includes[2]', False, False),
            ('slurp.includes.peep', False, False),
            ('slurp.includes', True, False),
            ('slurp[2]', False, False),
            ('slurp.backfill', True, False),
            ('slurp.read_size', True, False),
        ], [(path, exists, is_null) for path, exists, is_null in results])


class TestConfigSource(TestSource):

    def test_path(self):
        config = six.moves.configparser.ConfigParser()
        config.readfp(six.moves.StringIO("""\
[slurp]
state_dir = /var/lib/slurp
backfill = f
strict = F
read_size = 1024
buffer_size = 1048576
includes = /etc/slurp/conf.d/*.conf /etc/slurp/conf.d/*.py
"""))
        src = pilo.source.ConfigSource(config)
        results = []

        with pilo.ctx.push(src=src):
            results.append(self.result())
            with pilo.ctx.push(src='includes'):
                results.append(self.result())
                with pilo.ctx.push(src=0):
                    results.append(self.result())
                with pilo.ctx.push(src=1):
                    results.append(self.result())
                with pilo.ctx.push(src=2):
                    results.append(self.result())
                with pilo.ctx.push(src='peep'):
                    results.append(self.result())
                results.append(self.result())
            with pilo.ctx.push(src=2):
                results.append(self.result())
            with pilo.ctx.push(src='backfill'):
                results.append(self.result())
            with pilo.ctx.push(src='read_size'):
                results.append(self.result())

        self.assertEqual([
            ('', True, False),
            ('includes', False, False),
            ('includes[0]', False, False),
            ('includes[1]', False, False),
            ('includes[2]', False, False),
            ('includes.peep', False, False),
            ('includes', False, False),
            ('2', False, False),
            ('backfill', False, False),
            ('read_size', False, False)
        ], [(path, exists, is_null) for path, exists, is_null in results])


class TestJsonSource(TestSource):

    def test_path(self):
        src = pilo.source.JsonSource(json.dumps({
            'slurp': {
                'state_dir': '/var/lib/slurp',
                'backfill': False,
                'strict': False,
                'read_size': 1024,
                'buffer_size': 1048576,
                'poop': None,
                'includes': ['/etc/slurp/conf.d/*.conf', '/etc/slurp/conf.d/*.py'],
                }}))

        results = []

        with pilo.ctx.push(src=src):
            results.append(self.result())
            with pilo.ctx.push(src='slurp'):
                results.append(self.result())
                with pilo.ctx.push(src='includes'):
                    results.append(self.result())
                    with pilo.ctx.push(src=0):
                        results.append(self.result())
                    with pilo.ctx.push(src=1):
                        results.append(self.result())
                    with pilo.ctx.push(src=2):
                        results.append(self.result())
                    with pilo.ctx.push(src='peep'):
                        results.append(self.result())
                    results.append(self.result())
                with pilo.ctx.push(src=2):
                    results.append(self.result())
                with pilo.ctx.push(src='backfill'):
                    results.append(self.result())
                with pilo.ctx.push(src='read_size'):
                    results.append(self.result())

        self.assertEqual([
            ('', True, False),
            ('slurp', True, False),
            ('slurp.includes', True, False),
            ('slurp.includes[0]', True, False),
            ('slurp.includes[1]', True, False),
            ('slurp.includes[2]', False, False),
            ('slurp.includes.peep', False, False),
            ('slurp.includes', True, False),
            ('slurp[2]', False, False),
            ('slurp.backfill', True, False),
            ('slurp.read_size', True, False)
        ], [(path, exists, is_null) for path, exists, is_null in results])


class TestUnionSource(TestSource):

    def test_path(self):
        srcs = [
           pilo.source.DefaultSource({
               'a': {
                   'a.1': 1,
                   'a.2': 2,
                   'a.3': 3,
               },
               'b': [1, 2, 3.3],
           }, location='here.mem'),
           pilo.source.DefaultSource({
               'a': {
                   'a.3': 100,
                   'a.4': 4,
                   'a.5': 6,
               },
               'b': [3.1, 4.2, 5.3, 6.4],
           }, location='there.mem'),
        ]
        src = pilo.UnionSource(srcs, merge='combine')

        results = []

        with pilo.ctx.push(src=src):
            results.append(self.result())
            with pilo.ctx.push(src='a'):
                results.append(self.result())
                with pilo.ctx.push(src='a.2'):
                    results.append(self.result())
                with pilo.ctx.push(src='b'):
                    results.append(self.result())
                    with pilo.ctx.push(src=0):
                        results.append(self.result())
                    with pilo.ctx.push(src=1):
                        results.append(self.result())
                    with pilo.ctx.push(src=2):
                        results.append(self.result())

        self.assertEqual([
            ('', True, False),
            ('a', True, False),
            ('a.a.2', False, False),
            ('a.b', False, False),
            ('a.b[0]', False, False),
            ('a.b[1]', False, False),
            ('a.b[2]', False, False),
        ], [(path, exists, is_null) for path, exists, is_null in results])

    def test_merge(self):

        class MyForm(pilo.Form):

            a = pilo.fields.Dict(pilo.fields.String(), pilo.fields.Integer())

            b = pilo.fields.List(pilo.fields.Float())

        srcs = [
            pilo.source.DefaultSource({
                'a': {
                    'a.1': 1,
                    'a.2': 2,
                    'a.3': 3,
                },
                'b': [1, 2, 3.3],
            }),
            pilo.source.DefaultSource({
                'a': {
                    'a.3': 100,
                    'a.4': 4,
                    'a.5': 6,
                },
                'b': [3.1, 4.2, 5.3, 6.4],
            }),
        ]

        src = pilo.UnionSource(srcs, merge='combine')
        self.assertDictEqual(MyForm(src), {
            'a': {
                'a.1': 1, 'a.2': 2, 'a.3': 3, 'a.4': 4, 'a.5': 6
            },
            'b': [1.0, 2.0, 3.3, 3.1, 4.2, 5.3, 6.4],
        })

        src = pilo.UnionSource(srcs, merge='first')
        self.assertDictEqual(MyForm(src), {
            'a': {'a.1': 1, 'a.2': 2, 'a.3': 3},
            'b': [1.0, 2.0, 3.3],
        })

        src = pilo.UnionSource(srcs, merge='last')
        self.assertDictEqual(MyForm(src), {
            'a': {'a.3': 100, 'a.4': 4, 'a.5': 6},
            'b': [3.1, 4.2, 5.3, 6.4],
        })

    def test_error(self):
        srcs = [
            pilo.source.DefaultSource({
                'a': {
                    'a.1': 1,
                    'a.2': 2,
                    'a.3': 3,
                },
            }),
            pilo.source.DefaultSource({
                'a': 'barf'
            }),
        ]
        src = pilo.UnionSource(srcs, merge='combine')

        class MyForm(pilo.Form):

            a = pilo.fields.Dict(pilo.fields.String(), pilo.fields.Integer())

        errors = MyForm().map(src)
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], pilo.Invalid)
