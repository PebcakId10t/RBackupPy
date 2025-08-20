import logging
import re
import subprocess as SP
import typing
from collections import namedtuple

from rbackup.errors import(
    JobError,
    JobSuccess,
    UnsafeError
)
from rbackup.utils import(
    posix_path,
    env_update
)
if typing.TYPE_CHECKING:
    from .config import Config


class Job:
    """ Gets instantiated by its containing Group.\n
    Attrs (required):
        name: str               job name
        command: dict           "exec", "subcommand", "args"
    Attrs (optional):
        enabled: bool           available to run
        user: str               username for remote host
        description: str        brief description
        mode: str               job mode
        trunk: str              target subdir of root
        source: str             absolute path to local source
        sourceRemote: str       remote src path relative to root/trunk
        destination: str        absolute path to destination
        destinationRemote: str  remote dest path relative to root/trunk
        includeFrom: str        rclone/rsync --include-from
        excludeFrom: str        rclone/rsync --exclude-from
        filterFrom: str         rclone --filter-from/--filters-file
        resyncMode: str         resync compare mode (default: 'newer')
        prereq: list            list of prereq tasks
        onSuccess: list         list of tasks to complete after backup
    Attrs (computed):
        commandline: list       list of commandline args
    """

    def __init__(self, job: dict):
        """ Do not instantiate directly, use Config.get()
        """
        self.name               = job.get('name', '').strip()
        self.command            = job.get('command') or {}
        self.enabled            = job.get('enabled') or False
        self.user               = job.get('user', '').strip()
        self.description        = job.get('description', '').strip()
        self.mode               = job.get('mode') or 'push'
        self.source             = job.get('source', '').strip()
        self.destination        = job.get('destination', '').strip()
        # - None if not present
        self.trunk              = job.get('trunk', '').strip() if \
                                    'trunk' in job else None
        self.sourceRemote       = job.get('sourceRemote', '').strip() if \
                                    'sourceRemote' in job else None
        self.destinationRemote  = job.get('destinationRemote', '').strip() if \
                                    'destinationRemote' in job else None
        self.includeFrom        = posix_path(job['includeFrom']) if \
                                    'includeFrom' in job else None
        self.excludeFrom        = posix_path(job['excludeFrom']) if \
                                    'excludeFrom' in job else None
        self.filterFrom         = posix_path(job['filterFrom'])  if \
                                    'filterFrom' in job else None
        self.resyncMode         = job.get('resyncMode', 'newer').strip()
        self.commandline        = []
        self.logger             = logging.getLogger(f"JOB {self.name}")

        self.prereq = []
        if 'prereq' in job:
            tCount = 1            
            for task in job['prereq']:
                if 'command' not in task:
                    continue
                taskObj = namedtuple('PrereqTask', ['name', 'command', 'required'])
                t = taskObj(
                    task.get('name', f'<{tCount}>'),
                    task.get('command'),
                    task.get('required', False)
                )
                self.prereq.append(t)
                tCount += 1
        self.onSuccess = []
        if 'onSuccess' in job:
            tCount = 1
            for task in job['onSuccess']:
                if 'command' not in task:
                    continue
                taskObj = namedtuple('OnSuccessTask', ['name', 'command'])
                t = taskObj(
                    task.get('name', f'<{tCount}>'),
                    task.get('command')
                )
                self.onSuccess.append(t)
                tCount += 1


    def prepare(self, config: 'Config'):
        """ Prepare a job for running by completing its commandline.

        :param config: (Config) Config object
        :returns list:  the full commandline to be executed
        """
        self.config = config
        self.logger.info("Processing job...")

        command     = self.command.get('exec', '').strip()
        subcommand  = self.command.get('subcommand', '').strip()
        commandArgs = self.command.get('args', [])
        if isinstance(commandArgs, str):
            commandArgs = [commandArgs.split()]
        
        # sshLike: takes source and/or destination as user@remote:path, supports -v & -q
        sshLike = re.match("^(.*[\\\\/])?((cw)?rsync|scp|sftp|ssh)(.exe)?$", command)
        isRclone = re.match("^(.*[\\\\/])?rclone(.exe)?$", command)
        isRsync  = re.match("^(.*[\\\\/])?(cw)?rsync(.exe)?$",  command)

        args = [command]

        # Rclone subcommand comes first
        if isRclone:
            args.append(subcommand if subcommand else 'check')

        if isRclone or isRsync:
            # -v/-q, dryrun, logging, filtering, resync for rclone
            # verbose by default, extra verbose if -v used
            args.append(('-vv' if config.verbose else '-v') if not config.quiet else '-q')
            if config.dryRun:
                args.append('--dry-run')
            if config.logFile:
                # logFile should already be posix_path
                args += ['--log-file', config.logFile]
            if self.filterFrom:
                if isRclone and subcommand == 'bisync':
                    args += ['--filters-file', posix_path(self.filterFrom)]
                elif isRclone:
                    args += ['--filter-from', posix_path(self.filterFrom)]
            elif self.excludeFrom:
                args += ['--exclude-from', posix_path(self.excludeFrom)]
            elif self.includeFrom:
                args += ['--include-from', posix_path(self.includeFrom)]
            if isRclone and subcommand == 'bisync' and config.resync:
                args += ['--resync-mode', self.resyncMode]
        elif sshLike:
            # Just -v/-q
            if config.verbose:
                args.append('-v')
            elif config.quiet:
                args.append('-q')

        # Calculate remote, root, trunk
        user = self.command.get('user') or self.user or config.user
        root = config.root
        remote = config.remote
        remotePath = f"{remote}:{root}" if (remote and config.type != 'local') else f"{root}"
        if config.type == 'host':
            if sshLike and not re.match("^.*@.*$", remote):
                remote = f"{user}@{remote}"
                remotePath = f"{user}@{remotePath}"

        # Vars for substitution
        env_update({
            'user': user,
            'root': root,
            'remote': remote,
            'remotePath': remotePath,
        })

        # May contain vars itself that need parsing (eg. $user, $datetime)
        trunk = posix_path(self.trunk) if self.trunk is not None else \
                posix_path(config.trunk)

        env_update({
            'trunk': trunk
        })

        # Add remaining args
        args += [posix_path(arg) for arg in commandArgs]

        # "source": absolute path to source
        # "sourceRemote": remote path relative to root/trunk, may be empty
        if self.source:
            src = posix_path(self.source)
        elif self.sourceRemote is not None:
            src = posix_path(remotePath, trunk, self.sourceRemote)
        else:
            src = ''

        # "destination": absolute path to destination
        # "destinationRemote": remote path relative to root/trunk, may be empty
        if self.destination:
            dest = posix_path(self.destination)
        elif self.destinationRemote is not None:
            dest = posix_path(remotePath, trunk, self.destinationRemote)
        else:
            dest = ''

        # "destination": ".", could be useful to allow jobs to write to $PWD
        # but maybe dangerous if unintended?  os.path.normpath('') returns '.'
        if dest == '.':
            self.logger.warning("Destination is current working directory! "
                                "Check commandline if using --interactive")
            if not config.force:
                raise(UnsafeError("Won't use current directory (.) as destination. "
                                  "Use --force or set destination to environment "
                                  "variable (ex. $PWD)"))
        if src:
            args.append(src)
        if dest:
            args.append(dest)

        self.commandline = args
        self.logger.info(f"Command: {' '.join(self.commandline)}")
        return self.commandline


    def execute(self):
        """ Execute a backup job and its prerequisite and post-run tasks.

        """
        if self.prereq:
            count = 1
            for task in self.prereq:
                self.logger.info(f"Running prerequisite task #{count}: '{task.name}'")
                if not self.runTask(task):
                    raise JobError("Skipping pending task(s) due to "
                                   "failed prerequisite.")
                count += 1

        self.logger.info("Running job command now...")
        try:
            self.runJob()
        except JobSuccess as err:
            self.logger.info(err)
        except JobError as err:
            self.logger.error(f"Error running job: {err}")
            raise

        if self.onSuccess:
            count = 1
            for task in self.onSuccess:
                self.logger.info(f"Running postrun task #{count}: '{task.name}'")
                if not self.runTask(task):
                    raise JobError("Job postrun task has failed.")
                count += 1


    def runJob(self):
        """ Runs a backup job, reporting success or failure.  Success is raised
        just like an error but the caller must differentiate and reraise actual
        errors.
        """
        proc = SP.run(self.commandline)
        code = proc.returncode
        if code != 0:
            if re.match("rclone(.exe)?$", self.command['exec']) and code == 9:
                if '--error-on-no-transfer' in self.command['args']:
                    raise JobSuccess(errors="There was nothing to transfer.",
                                     exitcode=code)
            else:
                raise JobError("Job appears to have failed", exitcode=code)
        else:
            raise JobSuccess(exitcode=code)
        return True


    def runTask(self, task: object):
        """ Runs a prereq or postrun task.

        :returns: False if exit code was non-zero and task was marked required.
        True otherwise.
        """
        if hasattr(task, 'command'):
            cmd = [posix_path(arg) for arg in task.command]
            self.logger.info(f"shell> {' '.join(cmd)}")
            proc = SP.run(cmd)
            if proc.returncode != 0:
                self.logger.error(f"Task '{task.name}' appears to have failed with "
                                  f"exit code {proc.returncode}")
                if hasattr(task, 'required') and task.required:
                    return False
        return True


    @classmethod
    def filter_jobs(cls, jobs: list, backupMode: str = 'any',
                    enabledOnly = False):
        """ Returns an iterable  of jobs matching the criteria.  If backupMode
        is "any",  jobs with either mode ("push" or "pull") are returned, else
        only jobs matching the given mode are returned. If a job does not have
        a "mode" attribute, it is assumed to be "push" mode. If enabledOnly is
        True, only jobs that are marked as enabled are returned.

        :param jobs: (list) the unfiltered list of jobs
        :param backupMode: (str) backup mode jobs must support
        :param enabledOnly: (bool) whether to return only enabled jobs

        :returns (Generator): an iterable of matching jobs
        """
        for job in jobs:
            if backupMode == 'any' or \
                (not hasattr(job, 'mode') and backupMode == 'push') or \
                    (hasattr(job, 'mode') and backupMode == job.mode):
                if not enabledOnly or job.enabled:
                    yield job


    def debugDump(self):
        import pprint
        pprint.pprint(vars(self))
