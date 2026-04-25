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
import json
import hashlib
import hmac
import base64


class SecretProvider(object):
    """Abstract base class for all csmake secret providers.

    Subclasses implement load() (and optionally unlock()) for specific
    backends such as HashiCorp Vault, Docker secrets, cloud metadata
    services, etc.

    IMPORTANT: SecretProvider itself and the concrete subclasses in CsmakeCore
    (PlaintextFileProvider, ObfuscatedFileProvider) are NOT secure for
    production use.  They exist to provide a zero-dependency fallback.
    For real security use a provider from a csmake secrets support library.

    Providers do not need to hold all secret values in memory — get(key) is
    called lazily by Environment._lookupSecret() at resolution time, so a
    provider may fetch from a remote service, re-authenticate, or cache at
    its own discretion.

    Lifecycle:
        provider = MyProvider(namespace, source, log)
        provider.unlock(credential)   # optional for insecure providers
        provider.load()               # prepare; may or may not pre-fetch
        env.registerSecretProvider(namespace, provider)
        # ... build steps reference (((namespace:key))) or (((key))) ...
        provider.close()              # wipe / release resources"""

    INSECURE = True

    def __init__(self, namespace, source, log):
        self.namespace = namespace if namespace else ''
        self.source = source
        self.log = log
        self._secrets = {}

    def unlock(self, credential):
        """Prepare the provider using the given credential.  Called before
        load().  The base implementation is a no-op; insecure providers that
        ignore credentials are intentionally permissive."""
        pass

    def load(self):
        """Prepare access to the secret source.  Must be overridden.
        Implementations may pre-fetch all values, open a connection, or
        defer all I/O to get() depending on their backend."""
        raise NotImplementedError(
            "%s must implement load()" % self.__class__.__name__)

    def get(self, key):
        """Return the secret value as a plain str, or raise KeyError.
        Called lazily by Environment._lookupSecret() at substitution time.
        Environment is responsible for wrapping the result in ProtectedString;
        providers return plain str so that the core syntax layer owns the
        protection guarantee."""
        if key not in self._secrets:
            raise KeyError(
                "Secret '%s' not found in namespace '%s'" % (
                    key, self.namespace or '(default)'))
        return self._secrets[key]

    def keys(self):
        return list(self._secrets.keys())

    def close(self):
        """Overwrite and release all in-memory secret values."""
        for k in list(self._secrets.keys()):
            self._secrets[k] = '\x00' * len(self._secrets[k])
        self._secrets.clear()

    def _warnIfInsecure(self):
        if self.INSECURE:
            self.log.warning(
                "SECURITY WARNING: %s is not a secure secrets provider. "
                "Secrets may be stored in plaintext or with weak obfuscation. "
                "Do not use for production secrets.",
                self.__class__.__name__)


class PlaintextFileProvider(SecretProvider):
    """Loads secrets from a plaintext JSON file.

    INSECURE: Secrets are stored in plaintext on disk.  Suitable only for
    development environments or genuinely non-sensitive configuration values.

    File format — a flat JSON object:
        {
            "db_password": "s3cr3t",
            "api_key":     "abc123"
        }"""

    INSECURE = True

    def load(self):
        self._warnIfInsecure()
        try:
            with open(self.source) as fh:
                data = json.load(fh)
            if not isinstance(data, dict):
                raise ValueError("Secrets file must contain a JSON object")
            for k, v in data.items():
                self._secrets[str(k)] = str(v)
        except Exception as exc:
            raise IOError(
                "Failed to load secrets from '%s': %s" % (
                    self.source, str(exc)))


class ObfuscatedFileProvider(SecretProvider):
    """Loads secrets from an HMAC-XOR obfuscated file.

    INSECURE: This is obfuscation, not encryption.  A determined attacker
    with access to both the file and the unlock credential can read all
    secrets.  It provides minimal protection against casual disk inspection
    only — do not rely on it for genuine security.

    The file is produced by ObfuscatedFileProvider.obfuscate() and contains
    the base64-encoded XOR of the plaintext JSON with an HMAC-SHA256
    keystream derived from the unlock credential.

    The unlock credential is passed in via unlock(value) before load(),
    where value is typically read from an environment variable by the
    secrets csmake module."""

    INSECURE = True

    def __init__(self, namespace, source, log):
        SecretProvider.__init__(self, namespace, source, log)
        self._credential = None

    def unlock(self, credential):
        self._credential = credential

    def _keystream(self, key_bytes, length):
        """Produce an HMAC-SHA256 based keystream of the requested length."""
        stream = b''
        counter = 0
        while len(stream) < length:
            stream += hmac.new(
                key_bytes,
                str(counter).encode('utf-8'),
                hashlib.sha256).digest()
            counter += 1
        return stream[:length]

    def load(self):
        self._warnIfInsecure()
        if self._credential is None:
            raise ValueError(
                "ObfuscatedFileProvider requires unlock() before load()")
        try:
            key_bytes = self._credential.encode('utf-8')
            with open(self.source, 'rb') as fh:
                ciphertext = bytearray(base64.b64decode(fh.read()))
            keystream = bytearray(self._keystream(key_bytes, len(ciphertext)))
            plaintext = bytearray(
                a ^ b for a, b in zip(ciphertext, keystream))
            data = json.loads(plaintext.decode('utf-8'))
            if not isinstance(data, dict):
                raise ValueError("Decrypted content must be a JSON object")
            for k, v in data.items():
                self._secrets[str(k)] = str(v)
        except Exception as exc:
            raise IOError(
                "Failed to load obfuscated secrets from '%s': %s" % (
                    self.source, str(exc)))

    @staticmethod
    def obfuscate(plaintext_path, output_path, credential):
        """Utility: obfuscate a plaintext JSON secrets file for use with
        ObfuscatedFileProvider.

        plaintext_path  - path to the input plaintext JSON file
        output_path     - path to write the obfuscated output
        credential      - the unlock credential string (must match what will
                          be supplied to unlock() at load time)"""
        key_bytes = credential.encode('utf-8')
        with open(plaintext_path) as fh:
            content = bytearray(fh.read().encode('utf-8'))
        stream = b''
        counter = 0
        while len(stream) < len(content):
            stream += hmac.new(
                key_bytes,
                str(counter).encode('utf-8'),
                hashlib.sha256).digest()
            counter += 1
        keystream = bytearray(stream[:len(content)])
        ciphertext = bytearray(a ^ b for a, b in zip(content, keystream))
        with open(output_path, 'wb') as fh:
            fh.write(base64.b64encode(bytes(ciphertext)))
