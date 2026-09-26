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
"""Wheel (PEP 427) dist-info generation -- a pure, stdlib-only library.

csmake's own ``.csm`` package format is wheel-compatible: the payload files
are the same, hashed the same way (sha256), so one artifact can be valid in
both dialects.  This module supplies the dist-info trio (METADATA, WHEEL,
RECORD) plus top_level.txt so that no consumer -- core's own
CsmakeModulePackager, or csmake-packaging's WheelPackage for general Python
projects -- reimplements wheel-writing.  See
``docs/MODULE_ECOSYSTEM_DESIGN.md`` ("Package format: .csm as wheel").

Callers already have (or are already computing) per-file sha256 hashes for
their own manifest; ``build_dist_info`` takes those as input rather than
hashing files itself, so the work is never done twice.
"""

import base64
import csv
import hashlib
import io
import re

__all__ = [
    "pep427_digest",
    "escape_name_component",
    "dist_info_dirname",
    "generate_metadata",
    "generate_wheel_file",
    "generate_top_level",
    "generate_record",
    "build_dist_info",
]


def pep427_digest(data_bytes):
    """Return the PEP 427 RECORD digest for *data_bytes*: 'sha256=<b64url>'.

    Base64 is URL-safe and unpadded, per the wheel spec.
    """
    digest = hashlib.sha256(data_bytes).digest()
    encoded = base64.urlsafe_b64encode(digest).rstrip(b'=').decode('ascii')
    return 'sha256=%s' % encoded


def escape_name_component(text):
    """Escape *text* for use in a wheel filename or dist-info directory name.

    Per PEP 427, any run of non-alphanumeric characters becomes a single
    ``_``.  This must be applied identically everywhere a distribution name
    or version appears in wheel-adjacent naming -- tools that consume a
    wheel derive the dist-info directory name straight from the filename
    (``<escaped-name>-<escaped-version>.dist-info``), so if the archive's
    actual dist-info directory used different escaping (or none), those
    tools compute the wrong path and fail to find it.  Verified against the
    reference ``wheel`` package's own ``WheelFile`` reader.
    """
    return re.sub(r'[^\w.]+', '_', text)


def dist_info_dirname(name, version):
    """The ``<escaped-name>-<escaped-version>.dist-info`` directory name.

    Uses the same escaping as the wheel filename's distribution/version
    segments, so a consumer deriving the dist-info path from the filename
    finds it.
    """
    return '%s-%s.dist-info' % (
        escape_name_component(name), escape_name_component(version))


def _oneline(text):
    """Collapse whitespace/newlines to a single line (RFC822 header value)."""
    return re.sub(r'\s+', ' ', text).strip()


def generate_metadata(name, version, description=None, keywords=None,
                       homepage=None, authors=None, classifiers=None,
                       metadata_version='2.1', extra_headers=None):
    """Return the METADATA file content as bytes.

    *authors* is a list of ``(name, email-or-None)`` tuples.
    """
    lines = [
        'Metadata-Version: %s' % metadata_version,
        'Name: %s' % name,
        'Version: %s' % version,
    ]
    if description:
        lines.append('Summary: %s' % _oneline(description))
    if keywords:
        lines.append('Keywords: %s' % keywords)
    if homepage:
        lines.append('Home-page: %s' % homepage)
    for author_name, email in (authors or []):
        lines.append('Author: %s' % author_name)
        if email:
            lines.append('Author-email: %s' % email)
    for classifier in (classifiers or []):
        lines.append('Classifier: %s' % classifier)
    for key, value in (extra_headers or {}).items():
        lines.append('%s: %s' % (key, value))
    return ('\n'.join(lines) + '\n').encode('utf-8')


def generate_wheel_file(tag, generator='csmake', root_is_purelib=True,
                         build=None, wheel_version='1.0'):
    """Return the WHEEL file content as bytes.

    *tag* is the compatibility tag, e.g. ``'py3-none-any'``.
    """
    lines = [
        'Wheel-Version: %s' % wheel_version,
        'Generator: %s' % generator,
        'Root-Is-Purelib: %s' % ('true' if root_is_purelib else 'false'),
    ]
    if build:
        lines.append('Build: %s' % build)
    lines.append('Tag: %s' % tag)
    return ('\n'.join(lines) + '\n').encode('utf-8')


def generate_top_level(top_level_name):
    """Return the top_level.txt content as bytes."""
    return ('%s\n' % top_level_name).encode('utf-8')


def generate_record(file_hashes, record_archive_path):
    """Return the RECORD file content as bytes.

    *file_hashes* is ``{archive_path: value}`` where ``value`` is either raw
    file bytes (hashed here) or an already-computed ``(digest_str, size)``
    tuple -- so a caller that already hashed everything for its own
    manifest never re-hashes.  *record_archive_path* is RECORD's own path
    within the archive; it lists itself with an empty digest and size, per
    the wheel spec convention.
    """
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator='\n')
    for archive_path in sorted(file_hashes):
        value = file_hashes[archive_path]
        if isinstance(value, (bytes, bytearray)):
            digest = pep427_digest(value)
            size = len(value)
        else:
            digest, size = value
        writer.writerow([archive_path, digest, size])
    writer.writerow([record_archive_path, '', ''])
    return buf.getvalue().encode('utf-8')


def build_dist_info(name, version, file_hashes, description=None,
                     keywords=None, homepage=None, authors=None,
                     classifiers=None, tag='py3-none-any',
                     generator='csmake', root_is_purelib=True, build=None,
                     top_level_name=None, metadata_version='2.1'):
    """Return ``{archive_path: bytes}`` for a complete dist-info directory.

    *file_hashes* covers every OTHER file already placed in the archive
    (the payload) as ``{archive_path: bytes-or-(digest, size)}``; this
    function adds the dist-info files' own entries (including RECORD's
    entries for METADATA/WHEEL/top_level.txt) and returns just the
    dist-info files, ready to merge into the archive's file list alongside
    the payload.
    """
    dist_info = dist_info_dirname(name, version)
    metadata_bytes = generate_metadata(
        name, version, description, keywords, homepage, authors,
        classifiers, metadata_version=metadata_version)
    wheel_bytes = generate_wheel_file(tag, generator, root_is_purelib, build)
    top_level_bytes = generate_top_level(top_level_name or name)

    metadata_path  = '%s/METADATA' % dist_info
    wheel_path     = '%s/WHEEL' % dist_info
    top_level_path = '%s/top_level.txt' % dist_info
    record_path    = '%s/RECORD' % dist_info

    record_input = dict(file_hashes)
    record_input[metadata_path]  = metadata_bytes
    record_input[wheel_path]     = wheel_bytes
    record_input[top_level_path] = top_level_bytes
    record_bytes = generate_record(record_input, record_path)

    return {
        metadata_path:  metadata_bytes,
        wheel_path:     wheel_bytes,
        top_level_path: top_level_bytes,
        record_path:    record_bytes,
    }
