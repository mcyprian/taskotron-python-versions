import logging
if __name__ == '__main__':
    # Set up logging ASAP to see potential problems during import.
    # Don't set it up when not running as the main script, someone else handles
    # that then.
    logging.basicConfig()

import os
import sys

from libtaskotron import check

# before we import from pyversions, let's add our dir to sys.path
sys.path.insert(0, os.path.dirname(__file__))

from pyversions import log, two_three_check


INFO_URL = ('https://python-rpm-porting.readthedocs.io/en/'
            'latest/applications.html'
            '#are-shebangs-dragging-you-down-to-python-2')
BUG_URL = 'https://github.com/fedora-python/task-python-versions/issues'
TEMPLATE = '''These RPMs require both Python 2 and Python 3:
{rpms}

Read the following document to find more information and a possible cause:
{info_url}
Or ask at #fedora-python IRC channel for help.

If you think the result is false or intentional, file a bug against:
{bug_url}
'''

WHITELIST = (
    'eric',  # https://bugzilla.redhat.com/show_bug.cgi?id=1342492
    'pungi',  # https://bugzilla.redhat.com/show_bug.cgi?id=1342497
)


def run(koji_build, workdir='.', artifactsdir='artifacts'):
    '''The main method to run from Taskotron'''
    workdir = os.path.abspath(workdir)

    # find files to run on
    files = sorted(os.listdir(workdir))
    rpms = []
    for file_ in files:
        path = os.path.join(workdir, file_)
        if file_.endswith('.rpm'):
            rpms.append(path)
        else:
            log.debug('Ignoring non-rpm file: {}'.format(path))

    artifact = os.path.join(artifactsdir, 'output.log')
    detail = task_two_three(rpms, koji_build, artifact)

    output = check.export_YAML(detail)
    return output


def task_two_three(rpms, koji_build, artifact):
    '''Check whether given rpms depenss on Python 2 and 3 at the same time'''
    outcome = 'PASSED'
    bads = {}

    if not rpms:
        log.warn('No binary rpm files found')
    for path in rpms:
        filename = os.path.basename(path)
        log.debug('Checking {}'.format(filename))
        name, py_versions = two_three_check(path)
        if name is None:
            # RPM could not read that file, not our problem
            # error is already logged
            pass
        elif name in WHITELIST:
            log.warn('{} is excluded from this check'.format(name))
        elif len(py_versions) == 0:
            log.info('{} does not require Python, that\'s OK'.format(filename))
        elif len(py_versions) == 1:
            py_version = next(iter(py_versions))
            log.info('{} requires Python {} only, that\'s OK'
                     .format(filename, py_version))
        else:
            log.error('{} requires both Python 2 and 3, that\'s usually bad. '
                      'Python 2 dragged by {}. '
                      'Python 3 dragged by {}.'
                      .format(filename, py_versions[2], py_versions[3]))
            outcome = 'FAILED'
            bads[filename] = py_versions

    detail = check.CheckDetail(checkname='python-versions.two_three',
                               item=koji_build,
                               report_type=check.ReportType.KOJI_BUILD,
                               outcome=outcome)

    if bads:
        detail.artifact = artifact
        rpms = ''
        for rpm, py_versions in bads.items():
            rpms += ('{}\n'
                     ' * Python 2 dependency: {}\n'
                     ' * Python 3 dependecny: {}\n'.format(rpm,
                                                           py_versions[2],
                                                           py_versions[3]))
        with open(detail.artifact, 'w') as f:
            f.write(TEMPLATE.format(rpms=rpms,
                                    info_url=INFO_URL,
                                    bug_url=BUG_URL))
        names = ', '.join(str(k) for k in bads.keys())
        problems = 'Problematic RPMs:\n' + names
    else:
        problems = 'No problems found.'

    summary = 'python-versions {} for {}. {}'.format(
              outcome, koji_build, problems)
    log.info(summary)

    return detail


if __name__ == '__main__':
    run('test')
