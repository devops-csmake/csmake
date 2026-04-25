# <copyright>
# (c) Copyright 2026 Autumn Patterson
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or (at your
# option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
# </copyright>
import os
import json
import tempfile
import unittest
import importlib

# ProtectedString, SECRET_RE, _SECRET_ONLY_RE are defined in Environment
# (core syntax processing); SecretProvider is module support built on core.
import Environment
import SecretProvider
importlib.reload(Environment)
importlib.reload(SecretProvider)

from Environment import Environment, ProtectedString, SECRET_RE, _SECRET_ONLY_RE
from SecretProvider import SecretProvider, PlaintextFileProvider, ObfuscatedFileProvider
from Result import Result
from OutputTee import OutputTee


class _FakeEngine(object):
    def __init__(self):
        self.settings = {
            'dev-output': True, 'debug': False, 'verbose': False,
            'quiet': False, 'no-chatter': False, 'file-tracking': False,
            'keep-going': False,
        }
        self.log = None


class _FakeLog(object):
    def warning(self, *a, **kw): pass
    def error(self, *a, **kw): pass
    def info(self, *a, **kw): pass
    def devdebug(self, *a, **kw): pass
    def exception(self, *a, **kw): pass


def _makeDictProvider(namespace, data):
    """Minimal duck-typed provider backed by a plain dict."""
    class _DictProvider(object):
        def get(self, key):
            if key not in data:
                raise KeyError(key)
            return ProtectedString(data[key])
        def keys(self):
            return list(data.keys())
    p = _DictProvider()
    p.namespace = namespace or ''
    return p


class testProtectedString(unittest.TestCase):

    def test_holdsValue(self):
        ps = ProtectedString('s3cr3t')
        self.assertEqual(len(ps), 6)
        self.assertIn('s3cr3t', [ps])
        self.assertEqual('prefix-' + ps._raw(), 'prefix-s3cr3t')

    def test_reprRedacted(self):
        self.assertEqual(repr(ProtectedString('s3cr3t')), '***REDACTED***')

    def test_strRedacted(self):
        self.assertEqual(str(ProtectedString('s3cr3t')), '***REDACTED***')

    def test_formatRedacted(self):
        ps = ProtectedString('s3cr3t')
        self.assertEqual('%s' % ps, '***REDACTED***')
        self.assertEqual('{}'.format(ps), '***REDACTED***')

    def test_rawBypassesProtection(self):
        ps = ProtectedString('s3cr3t')
        raw = ps._raw()
        self.assertIsInstance(raw, str)
        self.assertNotIsInstance(raw, ProtectedString)
        self.assertEqual(raw, 's3cr3t')

    def test_subprocessListUsesValue(self):
        # subprocess receives the str buffer, not __str__.
        ps = ProtectedString('hunter2')
        self.assertEqual(list(ps), list('hunter2'))

        OutputTee.endAll()


class testSecretRE(unittest.TestCase):

    def test_matchesDefaultNamespace(self):
        m = SECRET_RE.search('(((my_key)))')
        self.assertIsNotNone(m)
        self.assertIsNone(m.group('namespace'))
        self.assertEqual(m.group('key'), 'my_key')

    def test_matchesEmptyNamespaceColon(self):
        # (((:key))) is equivalent to (((key))) — both resolve to default ns
        m = SECRET_RE.search('(((:my_key)))')
        self.assertIsNotNone(m)
        self.assertEqual(m.group('namespace'), '')
        self.assertEqual(m.group('key'), 'my_key')

    def test_matchesExplicitNamespace(self):
        m = SECRET_RE.search('(((prod:db_password)))')
        self.assertIsNotNone(m)
        self.assertEqual(m.group('namespace'), 'prod')
        self.assertEqual(m.group('key'), 'db_password')

    def test_matchesInsideLargerString(self):
        m = SECRET_RE.search('psql -p (((prod:db_pass))) %(host)s')
        self.assertIsNotNone(m)
        self.assertEqual(m.group('namespace'), 'prod')
        self.assertEqual(m.group('key'), 'db_pass')

    def test_noMatchWithoutTripleParens(self):
        self.assertIsNone(SECRET_RE.search('((key))'))
        self.assertIsNone(SECRET_RE.search('(key)'))
        self.assertIsNone(SECRET_RE.search('%(key)s'))
        self.assertIsNone(SECRET_RE.search('{key}'))
        self.assertIsNone(SECRET_RE.search('[~~key~~]'))

    def test_secretOnlyREWholeValue(self):
        self.assertIsNotNone(_SECRET_ONLY_RE.match('(((key)))'))
        self.assertIsNotNone(_SECRET_ONLY_RE.match('  (((ns:key)))  '))
        self.assertIsNotNone(_SECRET_ONLY_RE.match('(((:key)))'))
        self.assertIsNone(_SECRET_ONLY_RE.match('prefix(((key)))'))
        self.assertIsNone(_SECRET_ONLY_RE.match('(((key)))suffix'))

        OutputTee.endAll()


class testPlaintextFileProvider(unittest.TestCase):

    def setUp(self):
        self.log = _FakeLog()
        self._tmpfiles = []

    def tearDown(self):
        for p in self._tmpfiles:
            try:
                os.unlink(p)
            except OSError:
                pass

    def _writeJson(self, data):
        fd, path = tempfile.mkstemp(suffix='.json')
        self._tmpfiles.append(path)
        with os.fdopen(fd, 'w') as fh:
            json.dump(data, fh)
        return path

    def test_loadsKeys(self):
        path = self._writeJson({'password': 'hunter2', 'token': 'abc'})
        provider = PlaintextFileProvider('', path, self.log)
        provider.load()
        # Provider.get() returns plain str — ProtectedString wrapping is
        # Environment's responsibility, tested in testEnvironmentSecretSubstitution.
        self.assertEqual(provider.get('password'), 'hunter2')
        self.assertEqual(provider.get('token'), 'abc')

    def test_getReturnsPlainStr(self):
        path = self._writeJson({'k': 'v'})
        provider = PlaintextFileProvider('', path, self.log)
        provider.load()
        result = provider.get('k')
        self.assertIsInstance(result, str)
        self.assertNotIsInstance(result, ProtectedString)
        self.assertEqual(result, 'v')

    def test_missingKeyRaisesKeyError(self):
        path = self._writeJson({'k': 'v'})
        provider = PlaintextFileProvider('', path, self.log)
        provider.load()
        with self.assertRaises(KeyError):
            provider.get('missing')

    def test_keysReturnsAllKeys(self):
        path = self._writeJson({'a': '1', 'b': '2'})
        provider = PlaintextFileProvider('mynamespace', path, self.log)
        provider.load()
        self.assertEqual(sorted(provider.keys()), ['a', 'b'])

    def test_closeClearsSecrets(self):
        path = self._writeJson({'k': 'v'})
        provider = PlaintextFileProvider('', path, self.log)
        provider.load()
        provider.close()
        self.assertEqual(provider.keys(), [])

    def test_badFileRaisesIOError(self):
        provider = PlaintextFileProvider('', '/nonexistent/path.json', self.log)
        with self.assertRaises(IOError):
            provider.load()

        OutputTee.endAll()


class testObfuscatedFileProvider(unittest.TestCase):

    def setUp(self):
        self.log = _FakeLog()
        self._tmpfiles = []

    def tearDown(self):
        for p in self._tmpfiles:
            try:
                os.unlink(p)
            except OSError:
                pass

    def _makeObfuscated(self, data, credential):
        fd_plain, plain_path = tempfile.mkstemp(suffix='.json')
        fd_obf, obf_path = tempfile.mkstemp(suffix='.obf')
        self._tmpfiles += [plain_path, obf_path]
        os.close(fd_obf)
        with os.fdopen(fd_plain, 'w') as fh:
            json.dump(data, fh)
        ObfuscatedFileProvider.obfuscate(plain_path, obf_path, credential)
        return obf_path

    def test_roundtrip(self):
        obf_path = self._makeObfuscated({'secret': 'topsecret'}, 'my-cred')
        provider = ObfuscatedFileProvider('', obf_path, self.log)
        provider.unlock('my-cred')
        provider.load()
        self.assertEqual(provider.get('secret'), 'topsecret')

    def test_wrongCredentialFails(self):
        obf_path = self._makeObfuscated({'k': 'v'}, 'right')
        provider = ObfuscatedFileProvider('', obf_path, self.log)
        provider.unlock('wrong')
        with self.assertRaises(IOError):
            provider.load()

    def test_missingUnlockFails(self):
        obf_path = self._makeObfuscated({'k': 'v'}, 'cred')
        provider = ObfuscatedFileProvider('', obf_path, self.log)
        with self.assertRaises(ValueError):
            provider.load()

    def test_returnsPlainStr(self):
        obf_path = self._makeObfuscated({'k': 'v'}, 'cred')
        provider = ObfuscatedFileProvider('', obf_path, self.log)
        provider.unlock('cred')
        provider.load()
        result = provider.get('k')
        self.assertIsInstance(result, str)
        self.assertNotIsInstance(result, ProtectedString)
        self.assertEqual(result, 'v')

        OutputTee.endAll()


class testEnvironmentSecretSubstitution(unittest.TestCase):

    def _makeEnv(self):
        env = Environment(_FakeEngine())
        env.env['host'] = 'db.example.com'
        return env

    def test_noSecretsPassThrough(self):
        env = self._makeEnv()
        self.assertEqual(env.doSubstitutions('hello %(host)s'), 'hello db.example.com')

    def test_wholeValueReturnsProtectedString(self):
        env = self._makeEnv()
        env.registerSecretProvider('', _makeDictProvider('', {'db_pass': 'hunter2'}))
        result = env.doSubstitutions('(((db_pass)))')
        self.assertIsInstance(result, ProtectedString)
        self.assertEqual(str(result), '***REDACTED***')
        self.assertEqual(result._raw(), 'hunter2')

    def test_wholeValueWithWhitespaceReturnsProtectedString(self):
        env = self._makeEnv()
        env.registerSecretProvider('', _makeDictProvider('', {'k': 'v'}))
        self.assertIsInstance(env.doSubstitutions('  (((k)))  '), ProtectedString)

    def test_emptyNamespaceColonEqualsDefault(self):
        # (((:key))) and (((key))) are equivalent — both resolve default ns
        env = self._makeEnv()
        env.registerSecretProvider('', _makeDictProvider('', {'k': 'val'}))
        r1 = env.doSubstitutions('(((k)))')
        r2 = env.doSubstitutions('(((:k)))')
        self.assertEqual(r1._raw(), r2._raw())
        self.assertIsInstance(r1, ProtectedString)
        self.assertIsInstance(r2, ProtectedString)

    def test_embeddedSecretReturnsPlainStr(self):
        env = self._makeEnv()
        env.registerSecretProvider('', _makeDictProvider('', {'db_pass': 'hunter2'}))
        result = env.doSubstitutions('psql -p (((db_pass))) %(host)s')
        self.assertNotIsInstance(result, ProtectedString)
        self.assertEqual(result, 'psql -p hunter2 db.example.com')

    def test_explicitNamespace(self):
        env = self._makeEnv()
        env.registerSecretProvider('prod', _makeDictProvider('prod', {'token': 'abc123'}))
        result = env.doSubstitutions('(((prod:token)))')
        self.assertIsInstance(result, ProtectedString)
        self.assertEqual(result._raw(), 'abc123')

    def test_defaultAndNamespacedCoexist(self):
        env = self._makeEnv()
        env.registerSecretProvider('', _makeDictProvider('', {'k': 'default-val'}))
        env.registerSecretProvider('ns', _makeDictProvider('ns', {'k': 'ns-val'}))
        self.assertEqual(env.doSubstitutions('(((k)))')._raw(), 'default-val')
        self.assertEqual(env.doSubstitutions('(((ns:k)))')._raw(), 'ns-val')

    def test_namespaceUnionLaterOverwrites(self):
        env = self._makeEnv()
        env.registerSecretProvider('ns', _makeDictProvider('ns', {'k': 'first'}))
        env.registerSecretProvider('ns', _makeDictProvider('ns', {'k': 'second'}))
        self.assertEqual(env.doSubstitutions('(((ns:k)))')._raw(), 'second')

    def test_namespaceUnionAddsKeys(self):
        env = self._makeEnv()
        env.registerSecretProvider('ns', _makeDictProvider('ns', {'a': '1'}))
        env.registerSecretProvider('ns', _makeDictProvider('ns', {'b': '2'}))
        self.assertEqual(env.doSubstitutions('(((ns:a)))')._raw(), '1')
        self.assertEqual(env.doSubstitutions('(((ns:b)))')._raw(), '2')

    def test_undefinedSecretRaisesKeyError(self):
        env = self._makeEnv()
        with self.assertRaises(KeyError):
            env.doSubstitutions('(((missing_key)))')

    def test_undefinedNamespaceRaisesKeyError(self):
        env = self._makeEnv()
        with self.assertRaises(KeyError):
            env.doSubstitutions('(((badns:key)))')

    def test_variableAndSecretInSameValue(self):
        env = self._makeEnv()
        env.registerSecretProvider('', _makeDictProvider('', {'pass': 'pw'}))
        result = env.doSubstitutions('%(host)s:(((pass)))')
        self.assertEqual(result, 'db.example.com:pw')
        self.assertNotIsInstance(result, ProtectedString)

    def test_secretsNotFlushedByFlushAll(self):
        env = self._makeEnv()
        env.registerSecretProvider('', _makeDictProvider('', {'k': 'v'}))
        env.flushAll()
        self.assertEqual(env.doSubstitutions('(((k)))')._raw(), 'v')

    def test_lazyLookupCallsProviderEachTime(self):
        # Environment must not cache values — each resolution calls provider.
        call_count = [0]
        class _CountingProvider(object):
            def get(self, key):
                call_count[0] += 1
                return ProtectedString('value')
        env = self._makeEnv()
        env.registerSecretProvider('', _CountingProvider())
        env.doSubstitutions('(((k)))')
        env.doSubstitutions('(((k)))')
        self.assertEqual(call_count[0], 2)

    def test_tripleParensNotMistakenForOtherSyntax(self):
        env = self._makeEnv()
        env.env['key'] = 'value'
        self.assertEqual(env.doSubstitutions('%(key)s'), 'value')
        self.assertEqual(env.doSubstitutions('no-secrets-here'), 'no-secrets-here')

        OutputTee.endAll()
