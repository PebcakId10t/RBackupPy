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
    eprint
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
    errors = []
    user = config['user'] if 'user' in config else ''
    root = config['root'] = posix_path(config['root']) if 'root' in config else ''
    remote = config['remote'] if 'remote' in config else ''

    print(f'root at beginning of parseConfig: {root}')

    # Used below for type deduction when type not specified in the config
    hasRemote = ('remote' in args and args.remote) or config.get('remote')
    hasUser = ('remote' in args and re.match('^.*@.*$', args.remote)) or config.get('user')

    if 'type' not in config:
        if hasRemote and hasUser:
            eprint('Missing config type but "remote" and "user" given, assuming type is host')
            config['type'] = 'host'
        elif hasRemote:
            eprint('Missing config type but "remote" given, assuming type is cloud')
            config['type'] = 'cloud'
        else:
            eprint('Missing config type with no "remote", defaulting to local')
            config['type'] = 'local'

    if config['type'] not in ['local', 'cloud', 'host']:
        errors.append(f'{configPath}: config type invalid. ' 
            'Must be one of: ["local", "cloud", "host"]')
    if errors:
        raise BadConfigError(errors=errors)
    
    # --root overrides config['root'] for local backups
    # --remote overrides [user@]remote[:root] for cloud/host
    if 'localBackupRoot' in args:
        config['root'] = args.localBackupRoot
    elif 'remote' in args:
        remote = args.remote
        if re.match('^.*@.*$', remote):
            user, remote = remote.split('@', 2)
        if re.match('^.*:.*$', remote):
            remote, root = remote.split(':', 2)
        args.remote = config['remote'] = remote
        if user:
            config['user'] = user
        if root:
            config['root'] = root

    if 'trunk' not in args and 'trunk' not in config:
        # Hostname for local/cloud, empty string for host
        if config['type'] in ['local', 'cloud']:
            config['trunk'] = platform.node()
        else:
            config['trunk'] = ''
    elif 'trunk' in args:
        config['trunk'] = args.trunk

    # remote, root & trunk could be defined in the config or obtained from
    # commandline args (see above).  Warn if remote/root unset.  Relative
    # paths will start from the first non-empty path component.
    # ([remote:][root/][trunk/][destinationRemote])
    if not config.get('root'):
        eprint('Warning: "root" unset or empty string.  Should be root of backup.')
    if config['type'] in ['cloud', 'host'] and not config.get('remote'):
        eprint('Warning: No "remote" set.  Should be target machine/rclone remote.')

    # Don't create nonexistent root without --force
    root = config.get('root')
    if config['type'] == 'local' and root and not os.path.isdir(root):
        if not args.force:
            raise UnsafeError(errors=f"Local backup root '{root}' does not exist "
                              "and needs to be created.  Use --force")
        else:
            Path(root).mkdir(parents=True)

    # Default user is current if unset
    if not config.get('user'):
        config['user'] = getpass.getuser()

    # Merge in remaining script args...
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
