# <copyright>
# (c) Copyright 2025 Autumn Patterson
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
import re
import tarfile
import tempfile

try:
    import urllib.request as _urllib_request
except ImportError:
    import urllib as _urllib_request  # Python 2

_CACHE_ROOT = os.path.expanduser('~/.csmake/modules')
_GITHUB_ORG = 'devops-csmake'

# CamelCase -> kebab-case:  'NodeRuntime' -> 'node-runtime'
#                            'GHActions'   -> 'gh-actions'
#                            'ShellEnv'    -> 'shell-env'
def _to_kebab(name):
    # 'GHActions' -> 'GH-Actions' (run of caps before cap+lower)
    s = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1-\2', name)
    # 'Node-Runtime' -> 'Node-Runtime' / 'shell-Env' -> 'shell-Env'
    s = re.sub(r'([a-z0-9])([A-Z])', r'\1-\2', s)
    return s.lower()


class ModuleResolver(object):
    """Resolve csmake module names to local paths, downloading from the
    devops-csmake GitHub organisation when not found locally.

    Naming convention (CamelCase -> kebab -> package):
        'NodeRuntime'  -> 'node-runtime'  -> 'csmake-node-runtime'
        'DockerRuntime'-> 'docker-runtime'-> 'csmake-docker-runtime'
        'GHActions'    -> 'gh-actions'    -> 'csmake-gh-actions'
        'ShellEnv'     -> 'shell-env'     -> 'csmake-shell-env'

    Packages are cached under ~/.csmake/modules/<package-name>/ and must
    contain a CsmakeModules/ subdirectory to be considered valid."""

    def __init__(self, settings=None):
        self.settings = settings

    def resolve(self, module_name):
        """Return a local path containing CsmakeModules/<module_name>.py,
        downloading from GitHub if necessary.  Returns None on failure."""
        package = 'csmake-%s' % _to_kebab(module_name)
        cache_path = os.path.join(_CACHE_ROOT, package)

        if self._is_valid_package(cache_path):
            return cache_path

        return self._download(package, cache_path)

    # ------------------------------------------------------------------ #

    def _is_valid_package(self, path):
        return (os.path.isdir(path) and
                os.path.isdir(os.path.join(path, 'CsmakeModules')))

    def _download(self, package, dest):
        """Try to download package from devops-csmake on GitHub.
        Returns dest path on success, None on failure."""
        try:
            os.makedirs(dest)
        except OSError:
            pass  # already exists

        tmp = tempfile.mktemp(suffix='.tar.gz')
        try:
            downloaded = False
            for url in [
                'https://github.com/%s/%s/archive/refs/heads/main.tar.gz'
                    % (_GITHUB_ORG, package),
                'https://github.com/%s/%s/archive/refs/heads/master.tar.gz'
                    % (_GITHUB_ORG, package),
            ]:
                try:
                    _urllib_request.urlretrieve(url, tmp)
                    downloaded = True
                    break
                except Exception:
                    continue

            if not downloaded:
                try:
                    os.rmdir(dest)
                except OSError:
                    pass
                return None

            self._extract(tmp, dest)

            if not self._is_valid_package(dest):
                return None

            return dest

        except Exception:
            return None
        finally:
            try:
                os.unlink(tmp)
            except OSError:
                pass

    def _extract(self, tarball, dest):
        """Extract tarball into dest, stripping the top-level directory."""
        _extract_kwargs = {}
        if hasattr(tarfile, 'data_filter'):  # Python 3.12+
            _extract_kwargs['filter'] = 'data'
        with tarfile.open(tarball) as tar:
            for member in tar.getmembers():
                parts = member.name.lstrip('/').split('/', 1)
                if len(parts) < 2 or not parts[1]:
                    continue
                if '..' in parts[1].split('/'):
                    continue
                member.name = parts[1]
                tar.extract(member, dest, **_extract_kwargs)
