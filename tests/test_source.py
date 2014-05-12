from __future__ import with_statement

from ConfigParser import ConfigParser
import contextlib
import json
from StringIO import StringIO

import pilo

from . import TestCase


class TestSource(TestCase):

    @contextlib.contextmanager
    def push(self, view, part):
        view.append(pilo.context.SourcePart(part))
        try:
            yield
        finally:
            view.pop()


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

        view = []
        results = []
        path = src.path(view)
        results.append((str(path), path.exists, path.is_null))
        with self.push(view, 'slurp'):
            results.append((str(path), path.exists, path.is_null))
            with self.push(view, 'includes'):
                results.append((str(path), path.exists, path.is_null))
                with self.push(view, 0):
                    results.append((str(path), path.exists, path.is_null))
                with self.push(view, 1):
                    results.append((str(path), path.exists, path.is_null))
                with self.push(view, 2):
                    results.append((str(path), path.exists, path.is_null))
                with self.push(view, 'peep'):
                    results.append((str(path), path.exists, path.is_null))
                results.append((str(path), path.exists, path.is_null))
            with self.push(view, 2):
                results.append((str(path), path.exists, path.is_null))
            with self.push(view, 'backfill'):
                results.append((str(path), path.exists, path.is_null))
            with self.push(view, 'read_size'):
                results.append((str(path), path.exists, path.is_null))

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
        config = ConfigParser()
        config.readfp(StringIO("""\
[slurp]
state_dir = /var/lib/slurp
backfill = f
strict = F
read_size = 1024
buffer_size = 1048576
includes = /etc/slurp/conf.d/*.conf /etc/slurp/conf.d/*.py
"""))
        src = pilo.source.ConfigSource(config)

        view = []
        results = []
        path = src.path(view)
        results.append((str(path), path.exists, path.is_null))

        with self.push(view, 'includes'):
            results.append((str(path), path.exists, path.is_null))
            with self.push(view, 0):
                results.append((str(path), path.exists, path.is_null))
            with self.push(view, 1):
                results.append((str(path), path.exists, path.is_null))
            with self.push(view, 2):
                results.append((str(path), path.exists, path.is_null))
            with self.push(view, 'peep'):
                results.append((str(path), path.exists, path.is_null))
            results.append((str(path), path.exists, path.is_null))
        with self.push(view, 2):
            results.append((str(path), path.exists, path.is_null))
        with self.push(view, 'backfill'):
            results.append((str(path), path.exists, path.is_null))
        with self.push(view, 'read_size'):
            results.append((str(path), path.exists, path.is_null))

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

        view = []
        results = []
        path = src.path(view)
        results.append((str(path), path.exists, path.is_null))

        with self.push(view, 'slurp'):
            results.append((str(path), path.exists, path.is_null))
            with self.push(view, 'includes'):
                results.append((str(path), path.exists, path.is_null))
                with self.push(view, 0):
                    results.append((str(path), path.exists, path.is_null))
                with self.push(view, 1):
                    results.append((str(path), path.exists, path.is_null))
                with self.push(view, 2):
                    results.append((str(path), path.exists, path.is_null))
                with self.push(view, 'peep'):
                    results.append((str(path), path.exists, path.is_null))
                results.append((str(path), path.exists, path.is_null))
            with self.push(view, 2):
                results.append((str(path), path.exists, path.is_null))
            with self.push(view, 'backfill'):
                results.append((str(path), path.exists, path.is_null))
            with self.push(view, 'read_size'):
                results.append((str(path), path.exists, path.is_null))

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
