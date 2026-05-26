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
"""csmake module registry client.

Downloads, verifies, and caches .csm packages from the
devops-csmake/csmake-registry GitHub repository (or any configured
registry with the same layout).

Cache layout
------------
~/.csmake/
  registry/
    contents_listing.json        <- GitHub Contents API response for index/
    contents_listing.json.etag   <- ETag for the above
    index/
      csmake-ghactions.json      <- per-package index from registry repo
      csmake-ghactions.json.etag
      ...
    combined-index.json          <- client-built aggregate; rebuilt when sources change
    combined-index.json.mtime    <- unix timestamp of last refresh
  modules/
    csmake-ghactions/
      1.0.0/
        csmake-manifest.json     <- kept for optional re-verification
        CsmakeModules/
          GHActions.py
          ...
        GHActionsLibrary/
          __init__.py
          ...
"""

import hashlib
import json
import logging
import os
import shutil
import sys
import tempfile
import time
import zipfile

try:
    import urllib.request as _urllib_request
    import urllib.error as _urllib_error
except ImportError:                          # Python 2 fallback (best-effort)
    import urllib as _urllib_request
    _urllib_error = _urllib_request

_log = logging.getLogger(__name__)

# ── Paths ──────────────────────────────────────────────────────────────────
_CACHE_ROOT    = os.path.expanduser('~/.csmake/modules')
_REGISTRY_CACHE = os.path.expanduser('~/.csmake/registry')

# ── Default registry ────────────────────────────────────────────────────────
_REGISTRY_OWNER  = 'devops-csmake'
_REGISTRY_REPO   = 'csmake-registry'
_REGISTRY_BRANCH = 'main'
_GITHUB_API_BASE = 'https://api.github.com'
_RAW_BASE        = 'https://raw.githubusercontent.com'

_DEFAULT_REGISTRY_BASE = '%s/%s/%s/%s' % (
    _RAW_BASE, _REGISTRY_OWNER, _REGISTRY_REPO, _REGISTRY_BRANCH)

# ── How long the combined index is considered fresh without re-checking ─────
_COMBINED_INDEX_TTL = 3600   # 1 hour in seconds


# ── Helpers ─────────────────────────────────────────────────────────────────

def _sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def _atomic_write(path, data):
    """Write *data* (str or bytes) to *path* atomically via a temp file."""
    dir_ = os.path.dirname(path)
    if dir_:
        try:
            os.makedirs(dir_)
        except OSError:
            pass   # already exists
    fd, tmp = tempfile.mkstemp(dir=dir_ or '.')
    try:
        if isinstance(data, str):
            data = data.encode('utf-8')
        os.write(fd, data)
        os.close(fd)
        os.replace(tmp, path)
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# ── Main class ───────────────────────────────────────────────────────────────

class ModuleRegistry(object):
    """csmake module registry client.

    Typical call sequence
    ---------------------
    At csmake startup::

        ModuleRegistry().seed_sys_path()

    When a module cannot be found locally::

        path = ModuleRegistry(settings).find('GHActions')
        if path:
            # add path to module search paths and retry
    """

    def __init__(self, settings=None):
        self.settings = settings or {}
        self._registries = self._load_registries()

    # ── Public API ────────────────────────────────────────────────────────

    def seed_sys_path(self):
        """Add all cached package roots to ``sys.path``.

        Called once at csmake startup — pure local filesystem scan, no
        network access.  Installed packages (brew/deb) already live on
        sys.path; this only adds packages that were lazily downloaded to
        ``~/.csmake/modules/``.
        """
        if not os.path.isdir(_CACHE_ROOT):
            return
        for pkg_name in sorted(os.listdir(_CACHE_ROOT)):
            pkg_root = os.path.join(_CACHE_ROOT, pkg_name)
            if not os.path.isdir(pkg_root):
                continue
            versions = [
                v for v in os.listdir(pkg_root)
                if os.path.isdir(os.path.join(pkg_root, v))
            ]
            if not versions:
                continue
            best = sorted(versions, key=self._version_key)[-1]
            path = os.path.join(pkg_root, best)
            if path not in sys.path:
                sys.path.insert(0, path)
                _log.debug("seed_sys_path: added %s", path)

    def find(self, module_name):
        """Look up *module_name*, downloading its package if necessary.

        Returns the local package root (the directory whose ``CsmakeModules/``
        subdirectory contains *module_name*) on success, or ``None`` on
        failure.

        Also installs dependencies into the cache and adds their roots to
        ``sys.path`` so that companion library imports work immediately.
        """
        try:
            combined = self._get_combined_index()
        except Exception as e:
            _log.debug("ModuleRegistry.find: could not load index: %s", e)
            return None

        pkg_name = combined.get('module_index', {}).get(module_name)
        if not pkg_name:
            _log.debug("ModuleRegistry.find: '%s' not in index", module_name)
            return None

        return self.install(pkg_name, combined=combined)

    def install(self, package_name, version=None, combined=None):
        """Install *package_name* (downloading from the registry if needed).

        Parameters
        ----------
        package_name:
            Exact registry package name (e.g. ``'csmake-ghactions'``).
        version:
            Specific version string.  If ``None``, uses the ``latest``
            field from the registry index, or the highest version found.
        combined:
            Pre-loaded combined index dict (avoids a redundant parse).

        Returns the local package root on success, ``None`` on failure.
        """
        if combined is None:
            try:
                combined = self._get_combined_index()
            except Exception as e:
                _log.debug("ModuleRegistry.install: could not load index: %s", e)
                return None

        pkg_data = combined.get('packages', {}).get(package_name)
        if not pkg_data:
            _log.warning(
                "ModuleRegistry: package '%s' not found in registry index",
                package_name)
            return None

        if version is None:
            version = pkg_data.get('latest')
        if version is None:
            versions = list(pkg_data.get('versions', {}).keys())
            if versions:
                version = sorted(versions, key=self._version_key)[-1]
        if version is None:
            _log.warning(
                "ModuleRegistry: no version available for '%s'", package_name)
            return None

        ver_data = pkg_data.get('versions', {}).get(str(version))
        if not ver_data:
            _log.warning(
                "ModuleRegistry: version '%s' of '%s' not found in index",
                version, package_name)
            return None

        dest = os.path.join(_CACHE_ROOT, package_name, str(version))

        # Already installed?
        if os.path.isdir(dest):
            _log.debug(
                "ModuleRegistry: '%s@%s' already cached at %s",
                package_name, version, dest)
            if dest not in sys.path:
                sys.path.insert(0, dest)
            # Still resolve deps in case they weren't installed before
            self._install_dependencies(ver_data, combined)
            return dest

        url = ver_data.get('url')
        if not url:
            _log.warning(
                "ModuleRegistry: no download URL for '%s@%s'",
                package_name, version)
            return None

        sha256 = ver_data.get('sha256', '')

        _log.info(
            "ModuleRegistry: downloading %s@%s from %s",
            package_name, version, url)
        path = self._download_and_install(url, sha256, package_name, version, dest)
        if path is None:
            return None

        self._install_dependencies(ver_data, combined)
        return path

    def resolve_dependencies(self, manifest, combined=None):
        """Install all dependencies listed in a *csmake-manifest.json* dict.

        Convenience wrapper for use when the manifest is already available
        (e.g. after extracting a .csm package manually).
        """
        if combined is None:
            try:
                combined = self._get_combined_index()
            except Exception:
                return
        self._install_dependencies(manifest, combined)

    # ── Registry configuration ────────────────────────────────────────────

    def _load_registries(self):
        """Return list of registry base URLs from config, or the default."""
        config_path = os.path.expanduser('~/.csmake/config.json')
        if os.path.isfile(config_path):
            try:
                with open(config_path) as f:
                    config = json.load(f)
                registries = config.get('registries')
                if isinstance(registries, list) and registries:
                    return registries
            except Exception:
                pass
        return [_DEFAULT_REGISTRY_BASE]

    # ── Combined index ────────────────────────────────────────────────────

    def _get_combined_index(self):
        """Return the combined index dict, refreshing from registry if stale.

        The combined index is rebuilt from the cached per-package files
        whenever the combined-index.json is older than ``_COMBINED_INDEX_TTL``
        *and* the registry reports any changed files (via ETag checks).
        """
        combined_path = os.path.join(_REGISTRY_CACHE, 'combined-index.json')
        mtime_path    = combined_path + '.mtime'

        # Still fresh? Load directly from cache.
        if os.path.isfile(combined_path) and os.path.isfile(mtime_path):
            try:
                with open(mtime_path) as f:
                    last_refresh = float(f.read().strip())
                if time.time() - last_refresh < _COMBINED_INDEX_TTL:
                    with open(combined_path) as f:
                        return json.load(f)
            except Exception:
                pass

        # Refresh per-package files from registry (ETag-gated network calls).
        self._refresh_registry_cache()
        combined = self._build_combined_index()

        # Persist combined index and bump mtime.
        try:
            _atomic_write(combined_path, json.dumps(combined, indent=2))
            _atomic_write(mtime_path, str(time.time()))
        except Exception as e:
            _log.debug("ModuleRegistry: could not persist combined index: %s", e)

        return combined

    def _refresh_registry_cache(self):
        """Fetch/update all per-package index files from the first working registry.

        Uses the GitHub Contents API to list the ``index/`` directory, then
        conditionally fetches each per-package JSON using ETag headers.
        Returns ``True`` if any file was updated.
        """
        for registry_base in self._registries:
            try:
                pkg_names = self._list_registry_packages(registry_base)
                changed = False
                for name in pkg_names:
                    if self._fetch_package_index(registry_base, name):
                        changed = True
                return changed
            except Exception as e:
                _log.debug(
                    "ModuleRegistry: registry '%s' unavailable: %s",
                    registry_base, e)
                continue
        return False

    def _list_registry_packages(self, registry_base):
        """Return list of package names from *registry_base*'s ``index/`` dir.

        For raw.githubusercontent.com registries, translates to the GitHub
        Contents API so no ``git`` binary is required.  Falls back to a
        plain HTTP request for other registry types.

        Returns a list of package name strings (``<name>.json`` → ``<name>``).
        """
        api_url = self._registry_base_to_contents_api(registry_base)

        cache_path = os.path.join(_REGISTRY_CACHE, 'contents_listing.json')
        etag_path  = cache_path + '.etag'

        headers = {'User-Agent': 'csmake-module-registry/1.0'}
        if api_url:
            headers['Accept'] = 'application/vnd.github.v3+json'

        cached_etag = None
        if os.path.isfile(etag_path):
            try:
                with open(etag_path) as f:
                    cached_etag = f.read().strip()
                if cached_etag:
                    headers['If-None-Match'] = cached_etag
            except Exception:
                pass

        target_url = api_url if api_url else (
            registry_base.rstrip('/') + '/index/')

        try:
            req = _urllib_request.Request(target_url, headers=headers)
            with _urllib_request.urlopen(req, timeout=15) as resp:
                new_etag = resp.headers.get('ETag', '')
                data = resp.read()
                if new_etag:
                    _atomic_write(etag_path, new_etag)
                _atomic_write(cache_path, data)
        except _urllib_error.HTTPError as e:
            if e.code == 304:
                # Not modified — use cached listing
                pass
            else:
                raise
        except Exception:
            raise

        # Parse cached listing
        try:
            with open(cache_path) as f:
                entries = json.load(f)
        except Exception:
            return []

        # GitHub Contents API returns a list of objects with 'name' and 'type'.
        # A plain directory listing might be a dict of {filename: ...}.
        names = []
        if isinstance(entries, list):
            for entry in entries:
                if isinstance(entry, dict) and entry.get('type') == 'file':
                    fname = entry.get('name', '')
                    if fname.endswith('.json'):
                        names.append(fname[:-5])
        return names

    def _registry_base_to_contents_api(self, registry_base):
        """Translate a raw.githubusercontent.com URL to GitHub Contents API URL.

        ``https://raw.githubusercontent.com/<owner>/<repo>/<branch>``
        →  ``https://api.github.com/repos/<owner>/<repo>/contents/index?ref=<branch>``

        Returns ``None`` for non-GitHub URLs.
        """
        prefix = 'https://raw.githubusercontent.com/'
        if not registry_base.startswith(prefix):
            return None
        rest = registry_base[len(prefix):].rstrip('/')
        parts = rest.split('/')
        if len(parts) < 3:
            return None
        owner, repo, branch = parts[0], parts[1], parts[2]
        return '%s/repos/%s/%s/contents/index?ref=%s' % (
            _GITHUB_API_BASE, owner, repo, branch)

    def _fetch_package_index(self, registry_base, pkg_name):
        """Fetch ``index/<pkg_name>.json`` from *registry_base* with ETag caching.

        Returns ``True`` if the file was updated, ``False`` if unchanged (304)
        or on failure.
        """
        url        = '%s/index/%s.json' % (registry_base.rstrip('/'), pkg_name)
        cache_path = os.path.join(_REGISTRY_CACHE, 'index', '%s.json' % pkg_name)
        etag_path  = cache_path + '.etag'

        try:
            os.makedirs(os.path.dirname(cache_path))
        except OSError:
            pass

        headers = {'User-Agent': 'csmake-module-registry/1.0'}
        if os.path.isfile(etag_path):
            try:
                with open(etag_path) as f:
                    cached_etag = f.read().strip()
                if cached_etag:
                    headers['If-None-Match'] = cached_etag
            except Exception:
                pass

        try:
            req = _urllib_request.Request(url, headers=headers)
            with _urllib_request.urlopen(req, timeout=15) as resp:
                new_etag = resp.headers.get('ETag', '')
                data = resp.read()
                if new_etag:
                    _atomic_write(etag_path, new_etag)
                _atomic_write(cache_path, data)
                return True
        except _urllib_error.HTTPError as e:
            if e.code == 304:
                return False   # Not modified — cached file is current
            _log.debug(
                "ModuleRegistry: HTTP %s fetching index for '%s'",
                e.code, pkg_name)
            return False
        except Exception as e:
            _log.debug(
                "ModuleRegistry: failed to fetch index for '%s': %s",
                pkg_name, e)
            return False

    def _build_combined_index(self):
        """Build the combined index from all cached per-package JSON files.

        Returns a dict::

            {
              "module_index": {"GHActions": "csmake-ghactions", ...},
              "packages": {
                  "csmake-ghactions": { <per-package index contents> },
                  ...
              }
            }
        """
        index_dir = os.path.join(_REGISTRY_CACHE, 'index')
        combined  = {'module_index': {}, 'packages': {}}

        if not os.path.isdir(index_dir):
            return combined

        for fname in sorted(os.listdir(index_dir)):
            if not fname.endswith('.json'):
                continue
            fpath = os.path.join(index_dir, fname)
            try:
                with open(fpath) as f:
                    pkg_data = json.load(f)
            except Exception as e:
                _log.debug("ModuleRegistry: could not parse '%s': %s", fpath, e)
                continue

            pkg_name = pkg_data.get('name', fname[:-5])
            combined['packages'][pkg_name] = pkg_data

            for mod_name in pkg_data.get('provides_modules', []):
                combined['module_index'][mod_name] = pkg_name

        return combined

    # ── Download and install ──────────────────────────────────────────────

    def _install_dependencies(self, ver_data, combined):
        """Install all dependencies declared in *ver_data*."""
        for dep_name, dep_spec in ver_data.get('dependencies', {}).items():
            dep_version = self._resolve_version_spec(combined, dep_name, dep_spec)
            dep_path = self.install(dep_name, version=dep_version, combined=combined)
            if dep_path is None:
                _log.warning(
                    "ModuleRegistry: failed to install dependency '%s'", dep_name)

    def _download_and_install(self, url, expected_sha256, package_name, version, dest):
        """Download a .csm file, verify SHA256, extract to *dest*.

        Returns *dest* on success, ``None`` on any failure.
        """
        fd, tmp_path = tempfile.mkstemp(suffix='.csm')
        os.close(fd)
        try:
            try:
                _urllib_request.urlretrieve(url, tmp_path)
            except Exception as e:
                _log.warning(
                    "ModuleRegistry: download failed for '%s': %s", url, e)
                return None

            # Step 1: verify zip-level SHA256 (external integrity)
            if expected_sha256:
                actual = _sha256_file(tmp_path)
                if actual != expected_sha256:
                    _log.error(
                        "ModuleRegistry: SHA256 mismatch for %s@%s "
                        "(expected %s, got %s)",
                        package_name, version, expected_sha256, actual)
                    return None

            # Step 2: extract and verify per-file SHA256 (internal integrity)
            return self._extract_csm(tmp_path, package_name, version, dest)

        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    def _extract_csm(self, csm_path, package_name, version, dest):
        """Extract a .csm zip, verifying per-file SHA256 from the embedded manifest.

        Extraction is done to a temporary directory first; on success the
        directory is atomically renamed to *dest*.  Returns *dest* on success,
        ``None`` on any failure.
        """
        tmp_dest = dest + '.installing'
        if os.path.exists(tmp_dest):
            shutil.rmtree(tmp_dest, ignore_errors=True)

        try:
            with zipfile.ZipFile(csm_path, 'r') as zf:
                # ── Read and parse the embedded manifest first ──────────
                manifest_bytes = b''
                file_hashes    = {}
                try:
                    manifest_bytes = zf.read('csmake-manifest.json')
                    manifest       = json.loads(manifest_bytes)
                    file_hashes    = {
                        k: v.replace('sha256:', '')
                        for k, v in manifest.get('files', {}).items()
                    }
                except KeyError:
                    _log.warning(
                        "ModuleRegistry: no csmake-manifest.json in %s@%s; "
                        "skipping per-file verification",
                        package_name, version)
                except Exception as e:
                    _log.warning(
                        "ModuleRegistry: invalid manifest in %s@%s: %s",
                        package_name, version, e)

                # ── Extract all other files ─────────────────────────────
                try:
                    os.makedirs(tmp_dest)
                except OSError:
                    pass

                for member in zf.infolist():
                    name = member.filename

                    # Skip the manifest (written separately) and directories
                    if name == 'csmake-manifest.json' or name.endswith('/'):
                        continue

                    # Security: reject path traversal
                    segments = name.lstrip('/').split('/')
                    if '..' in segments:
                        _log.warning(
                            "ModuleRegistry: skipping unsafe path '%s'", name)
                        continue

                    out_path = os.path.join(tmp_dest, *segments)
                    out_dir  = os.path.dirname(out_path)
                    try:
                        os.makedirs(out_dir)
                    except OSError:
                        pass

                    with zf.open(member) as src, open(out_path, 'wb') as dst:
                        shutil.copyfileobj(src, dst)

                    # Per-file SHA256 check
                    if file_hashes and name in file_hashes:
                        actual = _sha256_file(out_path)
                        if actual != file_hashes[name]:
                            _log.error(
                                "ModuleRegistry: SHA256 mismatch on file '%s' "
                                "in %s@%s",
                                name, package_name, version)
                            shutil.rmtree(tmp_dest, ignore_errors=True)
                            return None

                # Write manifest alongside extracted files for re-verification
                if manifest_bytes:
                    with open(os.path.join(tmp_dest, 'csmake-manifest.json'), 'wb') as f:
                        f.write(manifest_bytes)

        except zipfile.BadZipFile as e:
            _log.error(
                "ModuleRegistry: corrupt .csm for %s@%s: %s",
                package_name, version, e)
            shutil.rmtree(tmp_dest, ignore_errors=True)
            return None

        # Atomic rename: tmp → dest
        try:
            os.makedirs(os.path.dirname(dest))
        except OSError:
            pass
        os.replace(tmp_dest, dest)

        # Immediately add to sys.path so library imports work in this session
        if dest not in sys.path:
            sys.path.insert(0, dest)
            _log.debug("ModuleRegistry: installed and added to sys.path: %s", dest)

        return dest

    # ── Version helpers ───────────────────────────────────────────────────

    def _version_key(self, v):
        """Sortable key for version strings.

        Converts each dot-separated segment to an int where possible so that
        ``'1.10.0' > '1.9.0'``.
        """
        parts = []
        for part in str(v).split('.'):
            try:
                parts.append((0, int(part)))
            except ValueError:
                parts.append((1, part))   # strings sort after ints
        return parts

    def _resolve_version_spec(self, combined, pkg_name, spec):
        """Resolve a version spec string (e.g. ``'>=1.0.0'``) to a concrete version.

        Current implementation: returns the ``latest`` field from the package
        index, or the highest available version.  Full semver constraint
        solving is left for a future iteration.
        """
        pkg_data = combined.get('packages', {}).get(pkg_name, {})
        latest   = pkg_data.get('latest')
        if latest:
            return latest
        versions = list(pkg_data.get('versions', {}).keys())
        if not versions:
            return None
        return sorted(versions, key=self._version_key)[-1]
