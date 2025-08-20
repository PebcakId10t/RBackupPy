import os
import platform
from pathlib import Path

def posix_path(path: str|Path, *paths) -> str:
    """ Takes a pathlike object and an optional list of paths to join with it.
    Returns a str using posix directory separators (/).  Also evaluates any
    environment variables in the string.  If the final component of the path to
    construct ends with a trailing separator, so will the output string.  (This
    is a workaround for pathlib.Path, which - for some reason - it was decided
    would always remove the goddamn trailing separator.)  All backslashes (\\)
    are replaced with forward slashes (/) for compatibility with most platforms.
    This is for working with local paths, not UNC.
    """
    last = str(path)
    if paths:
        last = str(paths[-1])
        path = Path(os.path.join(path, *paths)).as_posix()
    path = os.path.expandvars(path).strip().replace('\\', '/')
    # Remove any extra slashes
    path = os.path.normpath(path)
    # You have to do this again to change backslashes in a "normalized" Windows
    # path back to slashes
    if platform.system().lower() == 'windows':
        path = path.replace('\\', '/')
    if (last != '/' and last.endswith('/')) or last.endswith('\\') or last == '':
        path += '/'
    return path
