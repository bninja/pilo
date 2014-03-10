from ConfigParser import ConfigParser
import copy
import json
from StringIO import StringIO

import pilo

from . import TestCase


class TestDefaultSource(TestCase):

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
        path = src.path()
        results.append(copy.copy(path))
        with path.push('slurp'):
            results.append(copy.copy(path))
            with path.push('includes'):
                results.append(copy.copy(path))
                with path.push(0):
                    results.append(copy.copy(path))
                with path.push(1):
                    results.append(copy.copy(path))
                with path.push(2):
                    results.append(copy.copy(path))
                with path.push('peep'):
                    results.append(copy.copy(path))
                results.append(copy.copy(path))
            with path.push(2):
                results.append(copy.copy(path))
            with path.push('backfill'):
                results.append(copy.copy(path))
            with path.push('read_size'):
                results.append(copy.copy(path))

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
        ], [(str(path), path.exists, path.is_null) for path in results])


class TestConfigSource(TestCase):

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

        results = []
        path = src.path()
        results.append(copy.copy(path))

        with path.push('includes'):
            results.append(copy.copy(path))
            with path.push(0):
                results.append(copy.copy(path))
            with path.push(1):
                results.append(copy.copy(path))
            with path.push(2):
                results.append(copy.copy(path))
            with path.push('peep'):
                results.append(copy.copy(path))
            results.append(copy.copy(path))
        with path.push(2):
            results.append(copy.copy(path))
        with path.push('backfill'):
            results.append(copy.copy(path))
        with path.push('read_size'):
            results.append(copy.copy(path))

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
        ], [(str(path), path.exists, path.is_null) for path in results])


class TestJsonSource(TestCase):

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
        path = src.path()
        results.append(copy.copy(path))

        with path.push('slurp'):
            results.append(copy.copy(path))
            with path.push('includes'):
                results.append(copy.copy(path))
                with path.push(0):
                    results.append(copy.copy(path))
                with path.push(1):
                    results.append(copy.copy(path))
                with path.push(2):
                    results.append(copy.copy(path))
                with path.push('peep'):
                    results.append(copy.copy(path))
                results.append(copy.copy(path))
            with path.push(2):
                results.append(copy.copy(path))
            with path.push('backfill'):
                results.append(copy.copy(path))
            with path.push('read_size'):
                results.append(copy.copy(path))

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
        ], [(str(path), path.exists, path.is_null) for path in results])
