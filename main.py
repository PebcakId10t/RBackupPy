#!/usr/bin/env python3

""" Run rclone/rsync backups.  Backup jobs are defined in JSON config files and
processed in groups.  Use '-g' to run only certain backup groups while excluding
all others or '-G' to exclude only certain groups while running all others.
"""

import argparse
import logging
import platform
import sys
from datetime import datetime

from rbackup.constants import(
    g_default_log,
    g_default_config_name,
)
from rbackup.errors import(
    RBackupError
)
from rbackup.utils import(
    env_set,
    prompt_yes_or_no,
    SmartHelpFormatter,
    send_mail,
    get_mail_config,
)
from rbackup.classes.config import Config
from rbackup.classes.group import Group
from rbackup.classes.job import Job
filter_groups = Group.filter_groups
filter_jobs = Job.filter_jobs

# Get root logger
logging.root.name = 'main'
logger = logging.getLogger()


def run_backups(config: Config):
    if config.includeGroups:
        logger.debug(f"Backup groups included: {config.includeGroups}")
    elif config.excludeGroups:
        logger.debug(f"Backup groups excluded: {config.excludeGroups}")

    errors = []
    aborted = False

    groups = [g for g in filter_groups(config.groups, config.includeGroups,
                                       config.excludeGroups)]
    for group in groups:
        logger.debug(f"Group: '{group.name}'")
        jobs = [j for j in filter_jobs(group.jobs, config.mode,
                                       enabledOnly=False)]
        if len(jobs) < 1:
            logger.warning(f"No jobs in '{group.name}' matching mode '{config.mode}'")
            continue
        count = 1
        for job in jobs:
            if not job.enabled:
                logger.info(f"Job '{job.name}' disabled, skipping...")
                continue
            logger.debug(f"Job #{count}: '{job.name}'")
            cmdline = job.commandline
            try:
                if not cmdline:
                    cmdline = job.prepare(config)
                if not config.interactive or prompt_yes_or_no(f"Run job '{job.name}'?"):
                    job.execute()
            # Bad config, failed job
            except RBackupError as err:
                errors.append(err)
                logger.error(err)
                if group.skipOnFail:
                    logger.error("Skip on fail set, skipping remaining jobs "
                                f"in group '{group.name}'")
                    break
            # Anything else
            except Exception as ex:
                aborted = True
                errors.append(ex)
                logger.exception("An exception occurred:")
                break
            finally:
                count += 1
        if aborted:
            break
    if config.logFile and config.mailTo:
        mail_log(config, errors, aborted)


def mail_log(config: Config, errors=None, aborted=False):
    if not errors:
        errors = []
    mailConfig = get_mail_config()
    mailFrom = f"RBackup <{mailConfig.MAIL_FROM or mailConfig.MAIL_USER}>"
    subject = "Backup script error(s)" if len(errors) > 0 else "Backup script success"
    body =  f"Backup '{config.name}' " + \
            ("aborted " if aborted else "completed ") + \
            f"with {len(errors)} error(s).  See attached log.\n"
    send_mail(subject, body, config.mailTo, send_from=mailFrom,
              attachments=[config.logFile])


def main():
    env_set('machineName', platform.node())
    now = datetime.now()
    date = now.date().isoformat()
    time = f"{now.hour:02d}{now.minute:02d}{now.second:02d}"
    env_set('date', date)
    env_set('datetime', f"{date}-{time}")

    parser = argparse.ArgumentParser(
        prog="rbackup",
        formatter_class=SmartHelpFormatter,
        description=__doc__
    )
    parser.add_argument('-v', '--verbose', action='store_true',
        help="Increase verbosity")
    parser.add_argument('-q', '--quiet', action='store_true',
        help="Silence output")
    parser.add_argument('-d', '--debug', action='store_true',
        help="Print debug output")
    parser.add_argument('-i', '--interactive', action='store_true',
        help="Prompt before each backup job is run")
    parser.add_argument('configName', nargs='?', default=g_default_config_name,
        metavar='CONFIG',
        help="Name of the config to run (without .json extension), "
        "default: '%(default)s'")

    groups = parser.add_argument_group('Backup groups', 'Choose one')
    exclusive_g = groups.add_mutually_exclusive_group()
    exclusive_g.add_argument(
        '-g',
        '--groups',
        nargs='+',
        metavar='GROUP',
        dest='includeGroups',
        help="Backup groups to include (exclude all others), "
             "separated by whitespace."
    )
    exclusive_g.add_argument(
        '-G',
        '--no-groups',
        nargs='+',
        metavar='GROUP',
        dest='excludeGroups',
        help="Backup groups to exclude (include all others), "
             "separated by whitespace."
    )
    parser.add_argument(
        '-m',
        '--mode',
        metavar='MODE',
        choices=["push", "pull", "any"],
        default='push',
        help="Backup mode to run in "
             "(choices: [%(choices)s], default: '%(default)s')"
    )
    parser.add_argument(
        '-t',
        '--trunk',
        metavar='DIR',
        default=argparse.SUPPRESS,
        help="Subdirectory of backup root directory to use.  For 'host' backup "
             "types, this defaults to an empty string.  For all other types, "
             f"it is the system hostname ({platform.node()})"
    )
    remoteRoot = parser.add_argument_group('Remote/root', 'Choose one')
    exclusive_r = remoteRoot.add_mutually_exclusive_group()
    exclusive_r.add_argument(
        '-r',
        '--root',
        metavar='PATH',
        default=argparse.SUPPRESS,
        dest='localBackupRoot',
        help="Path to the local backup root (overrides config value, for local)"
    )
    exclusive_r.add_argument(
        '-R',
        '--remote',
        metavar='REMOTEPATH',
        default=argparse.SUPPRESS,
        dest='remote',
        help="Remote name/address or full path ([user@]remote[:root]) "+
             "(overrides config value(s), for cloud/host)"
    )
    parser.add_argument(
        '-n', '--dry-run', action='store_true', dest='dryRun',
        help="Dry run only"
    )
    parser.add_argument(
        '-s', '--resync', action='store_true',
        help="Run all bisync jobs in resync mode"
    )
    parser.add_argument(
        '-f', '--force', action='store_true',
        help="Force creation of backup root directory, or syncing to current directory ('.')"
    )

    ## - Logging/mailing options
    parser.add_argument(
        '-l',
        '--log-file',
        metavar='FILE',
        nargs='?',
        default=None,
        const=g_default_log,
        dest='logFile',
        help="Log to file.  If no file is specified, the default "
             f"({g_default_log}) will be used.  Specify 'none' to disable "
             "logging to file for this run, even if logging is enabled in your "
             "backup config file."
    )
    parser.add_argument(
        '-e',
        '--mail-to',
        metavar='EMAIL',
        action='append',
        dest='mailTo',
        help="Email log to recipient(s) (preface each with '-e')"
    )

    args = parser.parse_args()

    if type(args.logFile) is str and args.logFile.casefold() in \
            ["/dev/null", "null", "nul", "no", "none", "console"]:
        print(f"Logging to file DISABLED with '--log-file {args.logFile}')")
        args.logFile = False

    # Enable console logging
    logger.setLevel(logging.DEBUG)
    logFormatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(name)s - %(funcName)s() - %(message)s"
    )
    consoleHandler = logging.StreamHandler()
    if args.debug:
        consoleHandler.setLevel(logging.DEBUG)
    elif args.quiet:
        consoleHandler.setLevel(logging.ERROR)
    else:
        consoleHandler.setLevel(logging.INFO)
    consoleHandler.setFormatter(logFormatter)
    logger.addHandler(consoleHandler)

    # Get config (& optionally enable logging to file)
    try:
        config = Config.get(args)
    except RBackupError as err:
        logger.error(err.message)
    except Exception as ex:
        logger.exception(ex)
        raise
    else:
        if not args.quiet:
            print(f"Config path: {config.path}")
            if config.logFile:
                print(f"Logging to: {config.logFile}")

        run_backups(config)


if __name__ == "__main__":
    rc = 1
    try:
        main()
        rc = 0
    except Exception:
        logging.exception("An error occurred:")
    sys.exit(rc)
