# RBackupPy

Only tested on Linux systems as I don't have Python on Windows.

PowerShell version [here](https://github.com/PebcakId10t/RBackupPS)

Python backup script for `rclone`/`rsync`, intended for backing up individual
directories (not full system backups).  Backup jobs are defined in JSON config
files and processed in groups.  Use `-g group1 group2 ...` to run only certain
backup groups while excluding all others or `-G ...` to exclude only certain
groups while running all others.

A backup group has one or more jobs.  Jobs run sequentially and are typically
used to back up or restore a single directory or directory tree.

Everything is entered manually into JSON config files, there is no GUI or
config generator or anything like that.  Just a wrapper around rclone/rsync
with some predefined options for flexibility and some convenience features.

Configs are searched for under `$HOME/.config/rbackup` by default, but if this
doesn't suit you, just pass the script the full path to a file located elsewhere.
If no config name is provided to the script, it will look for the default at
`$HOME/.config/rbackup/rbackup.json`.

## Usage

```
main.py [-h] [-v] [-q] [-d] [-i] [-g GROUP [GROUP ...] | -G GROUP [GROUP ...]]
    [-m MODE] [-t DIR] [-r PATH | -R REMOTEPATH] [-n] [-s] [-f] [-l [FILE]]
    [-e EMAIL] [CONFIG]

positional arguments:
  CONFIG                Path to config, or name of config to run (with or
                        without .json extension), default: 'rbackup'

options:
  -h, --help            show this help message and exit
  -v, --verbose         Increase verbosity
  -q, --quiet           Silence output
  -d, --debug           Print debug output
  -i, --interactive     Prompt before each backup job is run
  -m, --mode MODE       Backup mode to run in (choices: [push, pull, any],
                        default: 'push')

  -t, --trunk DIR       Subdirectory of backup root directory to use. For
                        'host' backup types, this defaults to an empty string.
                        For all other types, it is the system hostname

  -n, --dry-run         Dry run only
  -s, --resync          Run all bisync jobs in resync mode
  -f, --force           Force creation of backup root directory, or syncing to
                        current directory ('.')

  -l, --log-file [FILE]
                        Log to file. If no file is specified, the default
                        ($HOME/.local/state/rbackup.log) will be used. Specify
                        'none' to disable logging to file for this run, even
                        if logging is enabled in your backup config file.

  -e, --mail-to EMAIL   Email log to recipient(s) (preface each with '-e')

Backup groups:
  Choose one

  -g, --groups GROUP [GROUP ...]
                        Backup groups to include (exclude all others),
                        separated by whitespace.

  -G, --no-groups GROUP [GROUP ...]
                        Backup groups to exclude (include all others),
                        separated by whitespace.

Remote/root:
  Choose one

  -r, --root PATH       Path to the local backup root (overrides config
                        value, for local)

  -R, --remote REMOTEPATH
                        Remote name/address or full path
                        ([user@]remote[:root]) (overrides config value(s),
                        for cloud/host)
```

## Backup types and attributes

Each config needs a `"type"` attribute that applies to all groups/jobs defined
in the config and affects the default options/behavior as well as what options
are available to configure.  The three backup types available are `"local"`,
`"cloud"`, and `"host"`.

`"local"` and `"cloud"` should be pretty self-explanatory.  `"host"` backups are
intended for replicating things like your music or video library onto other
local networked systems.

**If a config does not have a "type" attribute, the backup type will be guessed.**

If `"user"` and `"remote"` are both defined at the config level (or defined via
the `--remote` commandline arg), the assumption is that you're running a host
backup (one local networked system to another).  Host backup jobs using an
SSH-like program will include the username prepended onto the remote name/address
(`user@remote...`).

If no "user" is specified but "remote" is, the backup type is assumed to be cloud.
Cloud backups (using `rclone`) do not require the user to be specified as rclone
will handle authentication internally using its own configuration.

If neither "user" nor "remote" are defined anywhere, the backup type is assumed
to be local.

### Backup paths: root, trunk ...

> TL;DR:
>
> You don't need to worry about setting `root`, `remote`, or `trunk` in the
> config unless you want to be able to change your backup destination on the fly
> from the commandline.  Setting these in the config allows using relative paths
> to the source and destination and then being able to override the above path
> components using their respective commandline parameters when the situation
> calls for it (for example, when your backup drive changes or is mounted in a
> different location than usual).
>  
> If you'd rather keep things simple, you can just use the `source` and
> `destination` attributes for each job and set them to absolute paths.

Backup jobs have a source and destination.  These are either specified as absolute
paths or computed using relative ones.  Set absolute paths using the `source` and
`destination` attributes, or relative paths using `sourceRemote` and
`destinationRemote`.  See [job attributes](#job-attributes) below for more details.

A destination path separated into its constituent components:

```
[remote:]<root>/<trunk>/<destinationRemote>
```

This matches the typical rsync/rclone path:

```
[user@]remote_hostname_or_address:path/to/dest
```

`remote` and `root` are defined at the config level.  They will be shared by all
jobs.

`remote` is the name or address of the target machine (or `rclone` remote) and is
only used for remote backup types (cloud and host).

`root` is the root directory of the backup.  For local backups, it would typically
be the absolute path to the backup drive/volume/directory (ex. "/mnt/Backup").
For cloud backups, it would be the top level directory of the target remote
where your backups are stored (ex. my Google Drive has a top level folder called
"Backup").  For "host" backups, since these are intended for copying personal
files from one networked computer to another, this will usually be your home
directory on the remote system.

`trunk` is what subdirectory under the root to backup to.  The "trunk" for
most of my local and cloud backups is the hostname of the system the backup
came from, so this is the default for these.  Change this to whatever you want
with the `-t` script argument or by specifying a `"trunk"` value at the top
level of the config.  *Each job may also specify its own "trunk" attribute that
will override both of these.*

For host backups, the default trunk is an empty string, because host backups
are intended for backing up a directory like `~/Music` on one computer or "host"
to the same location on another one.

### Job modes - push and pull

Jobs have an optional `"mode"` attribute that can be set to either `"push"`
or `"pull"`.  This can be used as a means of separating backup jobs from
backup restoration jobs (and determining which jobs run when the script is
executed). When running the script in either "push" or "pull" mode, only jobs
matching that mode are run.

`"push"` jobs are meant to be backup jobs, while `"pull"` jobs restore backups,
"pulling" backed up files from a remote destination.

There are no technical differences between the two modes or how they work,
only semantics.  Source and destination are computed the same way for both
job types.  See above/below.

If a job does not specify a `"mode"`, it defaults to `"push"`.

### Source and destination

Source and destination can either be specified as absolute paths or relative
paths that depend on `"remote"`, `"root"` and `"trunk"`.  Absolute paths are
always used over relative ones if both are given.

#### Source

Use `"source"` to specify an absolute path to the backup source, or `"sourceRemote"`
to specify a ***remote*** subdirectory or path under `<root>/<trunk>`.  If both
attributes are set, `"source"` (the absolute path one) is used.

If *neither* attribute is set, then *no source will be appended to the command.*
Omit both source attributes for commands that do not need a source path (eg.
commands that only take a single path for the "destination", or no paths at all).

If `"sourceRemote"` is used but is set to an empty string, the source path will
be `[remote:]<root>/<trunk>/` (note the trailing slash).  This will cause
rclone/rsync to copy the contents of the remote "trunk" directory itself.

(If `"sourceRemote"` is used and set to an empty string, the script will ensure
that the combined path `[remote:]<root>/<trunk>/` ends with a trailing slash.
This ensures `rsync` copies the remote "trunk" directory's *contents*, not the
directory itself.  See notes on
[trailing separators](#path-variable-subtitution-and-separators).)

#### Destination

Use `"destination"` to specify an absolute path to the destination, or
`"destinationRemote"` to specify a *remote* subdirectory or path under
`<root>/<trunk>`.  If both are set, `"destination"` (the absolute path) is used.

As with source, if neither destination attribute is set, no destination will be
appended to the command. The same caveat applies here. Use this for commands that
only require one path (the *source* path) or none.

And as with `"sourceRemote"`, if `"destinationRemote"` is used but is set to an
empty string, the destination path is `[remote:]<root>/<trunk>`.  This will cause
rclone or rsync to copy/sync files to the trunk directory itself instead of a
subdirectory of it.

`"sourceRemote"` obviously only makes sense to use if the source is remote, as
would be the case with "pull" jobs (backup restoration), while `"destinationRemote"`
makes more sense with "push" mode.  But note that any of these attributes can be
used in any job type...

Jobs that use both remote-relative attributes may work entirely on the remote
side involving no local files (this may only work with `rclone` jobs which can
copy/move from one remote path to another), whereas the absolute attributes
allow using any arbitrary local or remote path for source and destination.  You
could also copy from one remote to another this way.

If you just want to keep things simple and not have to worry about all this
"root" and "trunk" crap, just set absolute paths with `"source"` and
`"destination"`. Everything else is pretty much optional and just there for
flexibility (changing drives/remotes on the fly, etc).

### Path variable subtitution and separators

All paths have [variable](#variables) subsitution performed and are converted
to POSIX-style paths (backslashes converted to forward slashes).  If a path (or
final path component, ie. `"sourceRemote"` / `"destinationRemote"`) ends with
a path separator, the trailing separator is retained.

Rules regarding trailing separators apply here.  If the source path given is a
directory and it does *not* end with a path separator, `rsync` will copy the
*directory* itself.  If it *does* end with a separator, it copies the directory
*contents*. `rclone` on the other hand will *always* try to copy contents if the
source path is a directory.  It does not (usually) care whether the path ends
with a separator or not, except with certain "subcommands". (`copyto` I believe
is picky about this and will error if one path ends with a separator and the other
does not.)

All paths have backslashes (`\\`) replaced with forward slashes (`/`) as Windows
accepts either one as a path separator, whereas backslashes do not work as
separators on Unix-like systems.

## Config attributes

- `"type"` - Type of backup config (`"local"`, `"cloud"`, or `"host"`)

- `"remote"` - Only used for `"cloud"` or `"host"` config types when dealing
with relative paths.  Remote name (`rclone`), address or hostname (`rsync`).

- `"root"` - Root directory for backups.  Used when dealing with relative paths.
For local backups, this might be the absolute path to your backup
drive/volume/directory.  For cloud/host, it could be the top level directory where
your backups are stored.  (It is the first part of a remote destination path
after the colon, as in `remote:root/trunk/...`. See rclone/rsync
examples online.)

- `"user"` - Optional.  Needed for rsync jobs.  If not specified, will default
to the user running the script.  Can be overridden by individual jobs.

- `"trunk"` - Subdirectory of backup root to use.  Second to last part of the
destination path when using relative destinations (`remote:root/trunk/...`).
Can be overridden by individual jobs.

- `"logFile"` - Set the path to the logfile to use.  If this is set, logging to
file can still be disabled for individual script runs by using `--log-file none`.
(This is helpful with `rclone` as it seems to only be capable of logging to either
the console or a file, not both at the same time.  Use `-l none` if you're in a
hurry to run your normal backup - ie. end of work day - and don't want to go
hunting through logfiles afterward to make sure it worked correctly.)

- `"groups"` - The array of backup groups

## Group attributes

- `"name"` - Group name.  Used for group inclusion/exclusion.

- `"skipOnFail"` - If set, jobs that exit with an error will cause subsequent
jobs in the group to be skipped.

- `"jobs"` - The array of backup jobs

## Job attributes

- `"enabled"` - Must be set to enable a job to run.

- `"name"` - Job name.

- `"description"` - Optional.  A short description.

- `"mode"` - Options are `"push"`, `"pull"`.  If not set, defaults to `"push"`.
Mostly just a way of controlling which jobs run when the script is called, but
could be used to logically separate backup restoration jobs from backup creation
ones.

- `"trunk"` - Overrides config `"trunk"` per job.  Subdirectory of backup root.

- `"user"` - Optional.  Overrides config-level "user" value for the job.

### Source

- `"source"` - The absolute path to the source.

- `"sourceRemote"` - Path to the remote source, relative to `"root"` and `"trunk"`
(`[remote:]<root>/<trunk>/<sourceRemote>`).  Only used if `"source"` is unset.

### Destination

- `"destination"` - The absolute path to the destination.

- `"destinationRemote"` - Path to the remote destination, relative to `"root"`
and `"trunk"` (`[remote:]<root>/<trunk>/<destinationRemote>`).  Only used if
`"destination"` is unset.

### Optional/extra

- `"resyncMode"` - For `rclone bisync` jobs, resync mode to use.  Defaults to
`"newer"`.

- `"filterFrom"` - `rclone` filtering, see [filtering](#filtering) below.

- `"includeFrom"` - `rsync` or `rclone` filtering, see below.

- `"excludeFrom"` - `rsync` or `rclone` filtering, see below.

### Required attributes

The only real requirements for a backup job are the source/destination and the
command, along with whatever arguments it needs.

See the info above if you want to use relative paths for source/destination.

Local backups will typically use `rclone` or `rsync`.  Cloud backups should only
use `rclone`, which will handle all the connection and user details itself, so no
"user" is required.  (Run `rclone config` to setup a new remote.)

Host backups could use `rclone` or `rsync` (or other SSH-like programs like `scp`
or `sftp`).  If using `rsync`/`scp`/`sftp`/`ssh`, you'll need to specify a "user"
if different from your current username or these programs may be unable to
authenticate.  Add this to the top of the config, or to each individual backup
job if they need different usernames.  (*Side note*: this is intended to be used
with key based auth and I haven't tested any of it with password entry.  If you
want to test it, be my guest.)

When using the `"source"` and `"destination"` absolute path attributes, "root",
"trunk", "remote" and "user" are not required or used at all (unless they're
included through a [variable](#variables)).

The `"command"` attribute of a backup job has three components - only one of
which is required.

`"exec"` (the program to run) can technically be whatever you want... there is
no checking to see if it's on some list of allowed programs or not.  If it's
`rclone`, `rsync`, or one of the other SSH-based commands (`scp`, `sftp`, or
`ssh`), then including `-v` or `-q` in the script commandline will automatically
include it in each job commandline as well.  If it's `rclone` or `rsync`,
including a filtering attribute (see below) in the job details will add the
appropriate commandline switch to the job.

Beyond that, I tried to make the script as flexible as possible while including
what I thought were sane defaults for a job runner.  It should be *technically*
possible to run any executable you want with any arguments you want.

`"args"` should be an array of commandline arguments to pass, if any.

If using rclone, `"subcommand"` is what rclone subcommand to use (`copy`, `sync`,
etc).  This is separated from the rest of the args so it can check if `bisync` is
being used and add the appropriate `resyncMode` flag if running jobs in resync mode.
If not specified, subcommand defaults to `check`.  (This is to prevent data loss
as `rclone check` should be nondestructive.)

## Other things

### Filtering

Include/exclude/filter files can be used by specifying them as a job attribute:

- `"includeFrom"`: works with rclone/rsync.  A file containing files/folders
to include.

- `"excludeFrom"`: works with rclone/rsync.  A file containing files/folders
to exclude.

- `"filterFrom"`: works with rclone.  Uses rclone's filtering syntax.

You can also just include the appropriate commandline arguments directly in your
`"args"` array... `"--include-from ..."`, `"--exclude-from ..."`,
`"--filter-from ..."`, etc.  No difference really.

For `rclone bisync` jobs, `"filterFrom"` is converted into `"--filters-file"`,
which is the parameter bisync uses for its checksummed filters file (as of
this writing).

### Variables

OS environment variables (`$USER`, `$HOST`, etc) are honored in string values
and a few internal variables are also made available for ... whatever
(path substitutions, etc):


- `$machineName`: Hostname, obtained by python's `platform.node()`.

- `$date`: Date the script was run in `YYYY-mm-dd` format.

- `$datetime`: Date and time the script was run in `YYYY-mm-dd-HHMMSS` format.

- `$user`: User, as specified in the job or config details with the `"user"`
attribute.  If unset, will be the current user running the script.

- `$root`: Backup root, as specified in the config file with `"root"` or on the
commandline with the `--root` argument.

- `$remote`: Remote name, as specified in the config with `"remote"` or on the
commandline with the `--remote` argument.

- `$trunk`: Trunk, as specified in the config with `"trunk"` or on the commandline
with the `-t` argument (or the default value for whatever backup type you're
running if no other value is set).

- `$remotePath`: Same as `$root` for local backups, or `$remote:$root` for host
or cloud backups.  For host backup jobs using `rsync`/`scp`/`sftp`/`ssh`,
`$user@` is also prepended.

- `$configName`: Name (stem only, no extension) of the config file.

- `$dashConfigName`: `"rbackup-"` appended with the config name (unless
using the default config `rbackup.json`, in which case it's just `"rbackup"`).
Might be useful for naming log files?

- `$configPath`: Full path to the config.

### Safety features

Use `--interactive` to confirm before running each job.  The commandline to
execute should be printed before the confirmation prompt for inspection.

Use `--dry-run` to append `--dry-run` to the `rclone`/`rsync` commandline and
test backups with verbose output before making changes.  (Verbose output is
enabled by default for `rclone` and `rsync`.  To be *extra* verbose, use `-v`.)

To make backup groups stop executing after any job in the group fails with an
error, set the `"skipOnFail"` attribute of the group to `true`.

``` jsonc
{
    // ...
    "groups": [
        {
            "name": "stuff",
            "skipOnFail": true,
            "jobs": [
                // ...
            ]
        }
    ]
}
```

Finally, jobs will not execute if the destination is set to the current directory
(`.`) without including the `--force` parameter.  This safety precaution exists
mainly because the Python path library's `normpath()` function converts an empty
string (`""`) to `.`  Misspelling the name of an attribute (eg. `"desination"`)
at one point could potentially wipe out your home directory.  If you want to
hardcode a backup job so that it always writes to the current directory, either
use `--force` or use the `$PWD` environment variable as the destination instead.

`--force` is also required when your chosen "root" directory does not yet exist.
This might prevent one from accidentally entering the wrong backup path when in
a hurry.

### Pre-exec and post-exec tasks

Jobs may have a `"prereq"` attribute with a list of prerequisite tasks that must
be executed before the job command can be run.  If a task is marked `"required"`,
the job will be skipped if the task fails.  Jobs may also have an `"onSuccess"`
attribute consisting of tasks to run once the job completes successfully.

``` json
"prereq": [
    {
        "required": true,
        "name": "tarball",
        "command": [
            "tar",
            "czvf",
            "$HOME/my_archive.tar.gz",
            "$HOME/my_dir/*.*"
        ]
    }
]
...
"onSuccess": [
    {
        "name": "rm tarball",
        "command": [
            "rm",
            "$HOME/my_archive.tar.gz"
        ]
    }
]
```

### Mailing

Mailing info will be read from a JSON config file pointed to by the environment
variable `$MAIL_CONFIG`.

This file is ***plaintext***.  It's *not* secure, and is not intended to be.
As such, don't store credentials for important accounts in this file, or any
other.  Use a throwaway account.

The config looks like this:

``` json
{
    "MAIL_USER": "<email login>",
    "MAIL_PASS": "<email password>",
    "MAIL_SERVER": "<smtp server>:<port>",
    "MAIL_FROM": "..."
}
```

The `MAIL_FROM` field is optional and should be a name and email address the way
they are typically displayed in email clients (`"My Name <my@email.domain>"`).
This is who the email will appear to have come from.

Note: Your email server will need to be configured to accept this "lower security"
login method.  I'm using an account configured with an "app password".

This uses the Python `smtplib` library.
