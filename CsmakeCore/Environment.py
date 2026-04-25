# <copyright>
# (c) Copyright 2026 Autumn Patterson
# (c) Copyright 2021 Autumn Patterson
# (c) Copyright 2017 Hewlett Packard Enterprise Development LP
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
import re
from CsmakeCore.MetadataManager import MetadataManager
from CsmakeCore.FileManager import MetadataFileTracker


class ProtectedString(str):
    """A str subclass that hides its value from repr/str/format to prevent
    accidental logging.

    WARNING: Protection is maintained only when the entire option value is a
    single (((key))) reference.  Embedding a secret in a larger string
    (e.g. "prefix-(((key)))-suffix") produces a regular str — protection is
    lost at that point.  This is an inherent limitation of string substitution;
    the class cannot protect secrets that have been concatenated into commands
    or file paths.

    As a str subclass the actual bytes are still accessible at the C level and
    through subprocess/os APIs, which is intentional — secrets must reach their
    destinations.  The goal is to stop them leaking through log calls."""

    def __new__(cls, value):
        return str.__new__(cls, value)

    def __repr__(self):
        return '***REDACTED***'

    def __str__(self):
        return '***REDACTED***'

    def __format__(self, format_spec):
        return '***REDACTED***'

    def _raw(self):
        """Return the underlying string value as a plain str.
        Use only where the actual secret value must be embedded (e.g. when
        building a command string).  Callers should document why they need
        this and be aware that protection is lost in the resulting string.

        str.__new__(str, self) calls __str__ in CPython and would return
        '***REDACTED***'.  Iterating the str buffer and rejoining produces
        a plain str from the underlying Unicode buffer without __str__."""
        return ''.join(self)


# Matches (((key))), (((:key))), or (((namespace:key))) anywhere in a string.
# The namespace group uses [^:)]* (zero or more chars) so that (((:key))) and
# (((key))) both resolve to the default namespace after normalisation.
#
# Triple-paren delimiters were chosen to avoid conflict with:
#   %(key)s   — environment variable substitution
#   {key}     — _parseBrackets
#   [~~k~~]   — FileManager axis substitution
#   <id(t:i)> — FILEDECL_RE file declarations
#   -(1-*)->  — MAP_RE cardinality
SECRET_RE = re.compile(
    r'\(\(\((?:(?P<namespace>[^:)]*):)?(?P<key>[^)]+)\)\)\)')

# Matches a string whose entire content (ignoring surrounding whitespace)
# is a single secret reference.  Used to decide whether to return a
# ProtectedString or a regular str from _resolveSecrets.
_SECRET_ONLY_RE = re.compile(
    r'^\s*\(\(\((?:(?P<namespace>[^:)]*):)?(?P<key>[^)]+)\)\)\)\s*$')


class Environment:
    """Shared environment for all build steps"""
    def __init__(self, engine):
        self.transPhase = {}
        self.env = {}
        self.engine = engine
        self.settings = engine.settings
        self.metadata = MetadataManager(self.engine.log, self)
        # namespace ('' for default) -> [provider, provider, ...]
        # Providers are stored by reference; secret values are never copied
        # into Environment.  _lookupSecret calls provider.get(key) lazily
        # at resolution time so that providers can manage their own memory,
        # caching, and re-authentication strategies.
        # Not cleared by flushAll — secrets are build-lifetime.
        self.secret_namespaces = {}

    def __repr__(self):
        return "Env: %s" % str(self.env)

    def addTransPhase(self, key, value):
        self.transPhase[key] = value
        self.env[key] = value

    def flushAll(self):
        self.env = self.transPhase.copy()
        self.metadata = MetadataManager(self.engine.log, self)
        # secret_namespaces intentionally preserved across phase flush

    def update(self, dictionary):
        tryAgain = False
        for key, value in dictionary.items():
            if key.startswith('**'):
                continue
            try:
                self.env[key] = self.doSubstitutions(value.strip())
            except:
                tryAgain = True
                self.engine.log.devdebug("update failed on '%s' - first pass" % key)
        if tryAgain:
            for key, value in dictionary.items():
                if key.startswith('**'):
                    continue
                self.env[key] = self.doSubstitutions(value.strip())

    def registerSecretProvider(self, namespace, provider):
        """Register a provider for the given namespace.
        namespace='' (or None) is the default namespace, referenced as
        (((key))) or (((:key))).
        Multiple providers registered under the same namespace are unioned;
        later registrations take precedence for colliding keys (same semantics
        as multiple [environment@...] sections).
        Secret values are never copied into Environment — provider.get(key)
        is called lazily each time a (((key))) reference is resolved."""
        ns = namespace if namespace else ''
        if ns not in self.secret_namespaces:
            self.secret_namespaces[ns] = []
        self.secret_namespaces[ns].insert(0, provider)

    def doSubstitutions(self, target):
        result = target % self.env
        return self._resolveSecrets(result)

    def _resolveSecrets(self, target):
        """Second substitution pass: expand (((key))), (((:key))), and
        (((ns:key))) references by calling registered secret providers.

        If the entire value is a single secret reference the result is a
        ProtectedString (repr/str redacted).  If the secret is embedded in a
        larger string the result is a regular str and protection is lost —
        this is an inherent limitation documented on ProtectedString."""
        if '(((' not in target:
            return target

        # Whole-value case: return a ProtectedString so accidental logging
        # of the option value shows ***REDACTED*** instead of the secret.
        m = _SECRET_ONLY_RE.match(target)
        if m:
            ns = m.group('namespace') or ''
            key = m.group('key')
            return self._lookupSecret(ns, key)

        # Mixed case: secret embedded in a larger string.  Protection is lost
        # but the value is functional.
        def _replace(match):
            ns = match.group('namespace') or ''
            key = match.group('key')
            value = self._lookupSecret(ns, key)
            # _raw() bypasses ProtectedString.__str__ so re.sub receives the
            # actual bytes rather than '***REDACTED***'.
            if isinstance(value, ProtectedString):
                return value._raw()
            return value

        return SECRET_RE.sub(_replace, target)

    def _lookupSecret(self, ns, key):
        """Lazily resolve (ns, key) by calling provider.get(key) on registered
        providers.  Providers are stored newest-first so iteration naturally
        gives later registrations priority on key collisions.
        Raises KeyError if unresolved."""
        if ns not in self.secret_namespaces:
            raise KeyError(
                "((({}:{})))".format(ns, key) if ns else "(((%s)))" % key)
        for provider in self.secret_namespaces[ns]:
            try:
                value = provider.get(key)
                # Wrap in ProtectedString here — providers return plain str
                # so the core syntax layer owns the protection guarantee.
                if isinstance(value, ProtectedString):
                    return value
                return ProtectedString(value)
            except KeyError:
                continue
        raise KeyError(
            "((({}:{})))".format(ns, key) if ns else "(((%s)))" % key)
