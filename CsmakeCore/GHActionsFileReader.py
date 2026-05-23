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
"""Translate a GitHub Actions workflow YAML into a csmake buildspec dict.

The returned dict is suitable for configparser.RawConfigParser.read_dict().
Each GHA job becomes a command@ section; uses: steps become GHActions@
sections; run: steps become GHActionsShell@ sections.  Jobs are ordered
topologically so that needs: dependencies are respected when running the
synthetic 'workflow' phase.
"""

try:
    import yaml as _yaml
    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False


def is_gha_workflow_file(path):
    return path.endswith('.yml') or path.endswith('.yaml')


def read_gha_workflow(path):
    """Return a dict suitable for RawConfigParser.read_dict() from a GHA YAML."""
    if not _HAS_YAML:
        raise RuntimeError(
            "PyYAML is required to use GitHub Actions workflow YAML files. "
            "Install with: pip install pyyaml")

    with open(path) as fh:
        workflow = _yaml.safe_load(fh)

    if not workflow or not isinstance(workflow, dict):
        raise RuntimeError("Invalid or empty workflow YAML: %s" % path)

    jobs = workflow.get('jobs') or {}
    if not jobs:
        raise RuntimeError("Workflow has no jobs: %s" % path)

    wf_env = _str_dict(workflow.get('env') or {})
    topo   = _topo_order(jobs)
    result = {}

    # ~~phases~~: informational only — documents available phases
    phases = {'default': workflow.get('name', 'GitHub Actions Workflow')}
    for job_id in topo:
        phases[job_id] = jobs[job_id].get('name', job_id)
    result['~~phases~~'] = phases

    # command@ (blank = default): sequences ALL jobs in dependency order.
    # This is what runs when the user just does `csmake --makefile=workflow.yml`.
    result['command@'] = {'%02d' % i: jid for i, jid in enumerate(topo)}

    # Sections for each job
    for job_id in topo:
        job     = jobs[job_id]
        job_env = dict(wf_env)
        job_env.update(_str_dict(job.get('env') or {}))

        step_ids = []

        for i, step in enumerate(job.get('steps') or []):
            if not step:
                continue

            raw_id     = step.get('id') or ('step%d' % i)
            section_id = '%s-%s' % (job_id, raw_id)

            uses = step.get('uses')
            run  = step.get('run')

            step_env = dict(job_env)
            step_env.update(_str_dict(step.get('env') or {}))

            opts = {}
            # Inject merged env as --env-KEY options
            for k, v in step_env.items():
                opts['--env-' + k] = v

            opts['--step-id'] = raw_id
            opts['--job-id']  = job_id

            if_cond = step.get('if')
            if if_cond is not None:
                opts['--if'] = str(if_cond)

            if uses:
                opts['--action'] = uses
                for k, v in (step.get('with') or {}).items():
                    opts[str(k)] = '' if v is None else str(v)
                module = 'GHActions'

            elif run is not None:
                opts['--script'] = str(run)
                opts['--shell']  = step.get('shell', 'bash')
                opts['--name']   = step.get('name') or raw_id
                wd = step.get('working-directory')
                if wd:
                    opts['--working-directory'] = str(wd)
                module = 'GHActionsShell'

            else:
                continue  # step has neither uses nor run

            result['%s@%s' % (module, section_id)] = opts
            step_ids.append(section_id)

        # command@<job_id> sequences this job's steps
        result['command@' + job_id] = {
            '%04d' % (i * 10): sid for i, sid in enumerate(step_ids)
        }

    return result


# ------------------------------------------------------------------ #
# Helpers                                                              #
# ------------------------------------------------------------------ #

def _str_dict(d):
    return {str(k): ('' if v is None else str(v)) for k, v in d.items()}


def _topo_order(jobs):
    order, seen = [], set()

    def visit(jid):
        if jid in seen:
            return
        seen.add(jid)
        needs = (jobs.get(jid) or {}).get('needs') or []
        if isinstance(needs, str):
            needs = [needs]
        for dep in needs:
            if dep in jobs:
                visit(dep)
        order.append(jid)

    for jid in jobs:
        visit(jid)
    return order
