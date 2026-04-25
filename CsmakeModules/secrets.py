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
from CsmakeCore.CsmakeModuleAllPhase import CsmakeModuleAllPhase
from CsmakeCore.SecretProvider import PlaintextFileProvider, ObfuscatedFileProvider


class secrets(CsmakeModuleAllPhase):
    """Purpose: Load secrets from a file and make them available for
       (((key))) or (((namespace:key))) substitution in subsequent steps.

       Type: Module   Library: csmake (core)
       Phases: *any*

       Options:
           source    - Path to the secrets file (JSON format).
                       Supports %(var)s environment variable substitution.
           namespace - (optional) Namespace for (((namespace:key))) refs.
                       Omit or leave empty for the default namespace,
                       referenced as (((key))).
                       Multiple sections sharing the same namespace are
                       merged; a later section overwrites colliding keys
                       (same union semantics as multiple [environment@...]
                       sections).
           unlock    - (optional) Name of an environment variable that holds
                       the unlock credential.  Required when obfuscate=yes.
           obfuscate - (optional) yes/no (default: no).
                       When yes, source is an HMAC-XOR obfuscated file
                       produced by ObfuscatedFileProvider.obfuscate().

       WARNING: This module is NOT secure for production secrets.
           obfuscate=no  — secrets stored in plaintext JSON on disk.
           obfuscate=yes — HMAC-XOR obfuscation only, not real encryption.
                           A determined attacker with file + credential access
                           can read all secrets trivially.
           For production use, replace this module with a provider from a
           csmake secrets support library (e.g. VaultSecrets).

       Secret references use triple-paren syntax to avoid any conflict with
       environment variable substitution, file specs, or other csmake
       parsing constructs:

           (((key)))              — default namespace
           (((namespace:key)))    — explicit namespace

       Example — plaintext (development only):
           [secrets@db-creds]
           source = %(WORKING)s/dev-secrets.json

           [Shell@connect]
           command = psql -U app -p (((db_password))) %(db_host)s

       Example — obfuscated, named namespace:
           [secrets@prod-db]
           source    = secrets/prod-db.obf
           namespace = prod
           unlock    = CSMAKE_PROD_DB_KEY
           obfuscate = yes

           [Shell@connect]
           command = psql -U app -p (((prod:db_password))) %(db_host)s

       To produce an obfuscated file from a plaintext JSON secrets file:
           from CsmakeCore.SecretProvider import ObfuscatedFileProvider
           ObfuscatedFileProvider.obfuscate(
               'plain.json', 'prod-db.obf', os.environ['CSMAKE_PROD_DB_KEY'])"""

    def __repr__(self):
        return "<<secrets step definition>>"

    def __str__(self):
        return "<<secrets step definition>>"

    def _doOptionSubstitutions(self, stepdict):
        # Suppress default option substitution.  We manually substitute
        # source and namespace in default() so that we control when and
        # how each option is resolved.
        pass

    def default(self, options):
        try:
            source = self.env.doSubstitutions(
                options.get('source', '').strip())
            namespace = self.env.doSubstitutions(
                options.get('namespace', '').strip())
            unlock_var = options.get('unlock', '').strip()
            obfuscate = options.get(
                'obfuscate', 'no').strip().lower() in ('yes', 'true', '1')

            if not source:
                self.log.error("'source' option is required")
                self.log.failed()
                return

            if obfuscate:
                if not unlock_var:
                    self.log.error(
                        "obfuscate=yes requires an 'unlock' env var name")
                    self.log.failed()
                    return
                credential = os.environ.get(unlock_var, '')
                if not credential:
                    self.log.error(
                        "Unlock env var '%s' is not set or is empty",
                        unlock_var)
                    self.log.failed()
                    return
                provider = ObfuscatedFileProvider(namespace, source, self.log)
                provider.unlock(credential)
            else:
                provider = PlaintextFileProvider(namespace, source, self.log)

            provider.load()
            self.env.registerSecretProvider(namespace, provider)
            self.log.passed()

        except Exception:
            self.log.exception("Failed to load secrets from '%s'", source)
            self.log.failed()

    def __getattr__(self, name):
        return self.default
