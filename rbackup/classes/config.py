import argparse
import getpass
import json
import logging
import os
import platform
import re
from pathlib import Path

from rbackup.constants import(
    g_default_config_path,
    g_default_log,
)
from rbackup.errors import(
    BadConfigError,
    UnsafeError
)
from rbackup.utils import(
    posix_path,
    env_set,
)
from rbackup.classes.group import Group

logger = logging.getLogger(__name__)


class Config:
    """ Do not instantiate directly, call class method Config.get(args)
    """
    def __init__(self, config: dict):
        self.name =             config.get('name')
        self.path =             config.get('path')
        self.user =             config.get('user')
        self.type =             config.get('type')

        # - Can be defined in config or set by script arg
        self.logFile =          config.get('logFile', None)
        self.remote =           config.get('remote', '')
        self.root =             config.get('root', '')
        self.trunk =            config.get('trunk', '')

        # - Set by script args
        self.localBackupRoot =  config.get('localBackupRoot', None)
        self.mode =             config.get('mode', None)
        self.includeGroups =    config.get('includeGroups', [])
        self.excludeGroups =    config.get('excludeGroups', [])
        self.mailTo =           config.get('mailTo', [])
        self.verbose =          config.get('verbose', False)
        self.quiet =            config.get('quiet', False)
        self.debug =            config.get('debug', False)
        self.interactive =      config.get('interactive', False)
        self.dryRun =           config.get('dryRun', False)
        self.resync =           config.get('resync', False)
        self.force =            config.get('force', False)


    @classmethod
    def get(cls, args: argparse.Namespace):
        """ Reads the config file specified in args.configName with the json
        library, enables logging to file if we want it, parses and merges the
        config with the commandline args, and instantiates each backup Group
        (which in turn instantiates each Job contained within).
        Returns a Config object containing our backup configuration.

        :param args: (Namespace) - commandline args
        :returns: Config object containing the backup configuration
        """
        configDict = openConfig(args)

        # If logFile == False instead of the default None, logging to file was
        # explicitly disabled on the commandline for this run.  Otherwise, we
        # need to check whether logging is enabled by commandline args or the
        # config and make it so.
        if args.logFile != False:  # noqa: E712
            setupFileLogging(configDict, args)

        configObj = parseConfig(configDict, args)
        configObj.groups = []

        try:
            for group in configDict['groups']:
                name = group.get('name')
                configObj.groups.append(Group(group))
        except Exception:
            logging.exception(f'Error processing backup group "{name}":')

        return configObj


def openConfig(args: argparse.Namespace) -> dict:
    """ Finds and opens the given config file, returning a dict
    """
    configPath = None
    configName = args.configName
    if Path(args.configName).is_file():
        configPath = Path(args.configName)
        configName = configPath.stem
    elif not Path(g_default_config_path).is_dir():
        raise FileNotFoundError(
            f"Config dir '{g_default_config_path}' does not exist. "
            "Create this directory and populate it with at least one "
            "backup config in JSON format."
        )
    else:
        path = Path(os.path.join(g_default_config_path, configName))
        paths = [path, path.with_suffix('.json'), path.with_suffix('.jsonc')]
        names = [p.name for p in paths]
        for p in paths:
            if p.is_file():
                configPath = p
                break
        if not configPath:
            ls = [item.stem for item in Path(g_default_config_path).glob('*.json*')]
            raise FileNotFoundError(
                f"No config named '{configName}' in {g_default_config_path} - "
                f"tried: {names}.  Configs available: {ls}"
            )

    with open(configPath, 'r') as file:
        data = file.read()
    config = json.loads(re.sub("//.*", "", data, flags=re.MULTILINE))

    # Save name & path
    config['path'] = configPath
    config['name'] = configName

    # Store these in env to allow referencing them in log names, etc
    env_set('configPath', configPath)
    env_set('configName', configName)
    env_set('dashConfigName',
            ('rbackup' if configName=='rbackup' else f'rbackup-{configName}'))

    return config


def parseConfig(config: dict, args: argparse.Namespace) -> Config:
    """ Parses config, fills in missing defaults and returns a Config object
    """
    configPath = config['path']
    user, root, remote = '', '', ''

    # If user & root are defined separately in the config, we don't want them to
    # be overridden by config['remote'] if it's defined like 'user@remote:root'
    # (maybe the user defined it like this by habit/mistake?).  Separate user &
    # root values should probably win here, but we do want to allow these to be
    # overridden if the commandline param --remote is used with the same syntax
    # (--remote 'user@remote:root').  Handle/set config values, then allow args
    # to override.
    configUser = config.get('user', '')
    configRoot = config.get('root', '')

    remote = config.get('remote', '')
    if re.match('^.*@.*$', remote):
        user, remote = remote.split('@', 1)
    if re.match('^.*:.*$', remote):
        remote, root = remote.split(':', 1)
    config['remote'] = remote
    # If user and/or root are present in config['remote'], but not defined
    # separately, we're clear to go ahead and set them here.
    if user and not configUser:
        config['user'] = user
    if root and not configRoot:
        config['root'] = root

    # Commandline overrides - only one of these will be set.
    # --root overrides config['root'] for local (param dest is 'localBackupRoot')
    # --remote overrides [user@]remote[:root] for cloud/host
    if 'localBackupRoot' in args:
        config['root'] = args.localBackupRoot
    elif 'remote' in args:
        remote = args.remote
        if re.match('^.*@.*$', remote):
            user, remote = remote.split('@', 1)
        if re.match('^.*:.*$', remote):
            remote, root = remote.split(':', 1)
        # Need to backfill args.remote so it doesn't overwrite config.remote when
        # we merge the two dicts at the end of this function, otherwise if you
        # use --remote 'user@remote' you get duplicate user (user@user@remote)
        args.remote = config['remote'] = remote
        if user:
            config['user'] = user
        if root:
            config['root'] = root

    # Support vars like $HOME, etc in root
    config['root'] = posix_path(config['root']) if 'root' in config else ''

    # Infer backup type if not specified in config, based on what values are set
    if 'type' not in config:
        msg = 'Missing config type'
        haveRemote, haveUser = config.get('remote'), config.get('user')
        if haveRemote and haveUser:
            logger.warning(f'{msg} - have remote and user so assuming type HOST')
            config['type'] = 'host'
        elif haveRemote:
            logger.warning(f'{msg} - have remote so assuming type CLOUD')
            config['type'] = 'cloud'
        else:
            logger.warning(f'{msg} - no remote so assuming type LOCAL')
            config['type'] = 'local'

    # Double check type is defined/inferred correctly & lowercase
    if str(config.get('type', '')).lower() not in ['local', 'cloud', 'host']:
        raise BadConfigError(errors=[f'{configPath}: config type invalid. '
            'Must be one of: ["local", "cloud", "host"]'])
    config['type'] = str(config['type']).lower()

    # Trunk default/override - hostname for local/cloud, empty for host
    if 'trunk' not in args and 'trunk' not in config:
        if config['type'] in ['local', 'cloud']:
            config['trunk'] = platform.node()
        else:
            config['trunk'] = ''
    elif 'trunk' in args:
        config['trunk'] = args.trunk

    # If backup type specified but root/remote were never defined, issue warning.
    # (These should only be required if using "relative" paths)
    if not config.get('root'):
        logger.warning('"root" unset or empty string.  Should be root of backup.')
    if config['type'] in ['cloud', 'host'] and not config.get('remote'):
        logger.warning(f"Backup type is {config['type']} but no remote set.  "
                       "Should be target machine/rclone remote.")

    # Don't create nonexistent local root without --force
    root = config.get('root')
    if config['type'] == 'local' and root and not os.path.isdir(root):
        if not args.force:
            raise UnsafeError(errors=f"Local backup root '{root}' does not exist "
                              "and needs to be created.  Use --force")
        else:
            Path(root).mkdir(parents=True)

    # Lastly, pick a default user if unset, so variable expansion works on it
    if not config.get('user'):
        config['user'] = getpass.getuser()

    # Merge dicts (args overwrite config)
    config = {**config, **args.__dict__}

    return Config(config)


def setupFileLogging(config: dict, args: argparse.Namespace):
    """ Sets up logging to file in the root logger
    """
    rootLogger = logging.getLogger()
    logFormatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(name)s - %(funcName)s() - %(message)s"
    )
    logFile = None
    if args.logFile:
        logFile = posix_path(args.logFile)
    elif 'logFile' in config and config['logFile']:
        logFile = posix_path(config['logFile'])
    if args.mailTo and not logFile:
        logFile = g_default_log
    if logFile:
        Path(logFile).parent.mkdir(parents=True, exist_ok=True)
        # Truncate file and then reopen with append mode
        with open(logFile, 'w') as f:
            f.close()
        fileHandler = logging.FileHandler(logFile, mode="a")
        fileHandler.setLevel(logging.DEBUG)
        fileHandler.setFormatter(logFormatter)
        rootLogger.addHandler(fileHandler)
    args.logFile = config['logFile'] = logFile
