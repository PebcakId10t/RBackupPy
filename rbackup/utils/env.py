import os

def env_backup():
    """ Back up all environment variables.
    """
    global env_original
    env = os.environ
    if 'env_original' not in globals():
        env_original = {}
    for k, v in env.items():
        env_original.update({k: v})

def env_set(key: str, val: str):
    """ Add/update a single environment variable
    """
    global env_original
    env = os.environ
    if 'env_original' not in globals():
        env_original = {}
    if not key or type(key) is not str:
        raise ValueError("Missing or invalid key, str type required")
    # Pre-existing var, back up before modifying
    if key in env and key not in env_original:
        env_original.update({key: env.get(key)})
    # New var
    elif key not in env:
        env_original.update({key: None})
    # Push new value
    env.update({key: str(val)})

def env_update(other: dict, **kwargs):
    """ Update/extend environment with another dict or iterable
    of key/value pairs
    """
    for k, v in other.items():
        env_set(str(k), v)
    for k, v in kwargs.items():
        env_set(k, v)

def env_get(key: str, default=None):
    """ Get an environment variable
    """
    env = os.environ
    return env.get(key, default)

def env_restore(key: str = None):
    """ Restore a single environment variable from modification or deletion,
    or all modified/deleted environment variables if key is None
    """
    import sys
    if 'env_original' not in globals():
        pass
    else:
        global env_original
        env = os.environ
        if key:
            if type(key) is not str:
                raise ValueError("Invalid key, str type required")
            # Restore a single environment variable...
            if key in env:
                # Unchanged / same as previous value
                if env.get(key) == env_original.get(key):
                    print(f"env('{key}'): value is unmodified", file=sys.stderr)
                # Added by env_set()?
                elif key in env_original and env_original.get(key) is None:
                    # Remove both value & backup
                    del env[key]
                    del env_original[key]
                # Modified by env_set()?
                elif key in env_original:
                    # Restore value & remove backup
                    env.update({key: env_original.get(key)})
                    del env_original[key]
            # Pre-existing var deleted by env_remove()?
            elif key in env_original:
                # Restore value & remove backup
                env.update({key: env_original.get(key)})
                del env_original[key]
        else:
            # Remove anything extra we added...
            for k, v in env.items():
                # Added by env_set()?
                if k in env_original and env_original.get(k) is None:
                    # Remove both value & backup
                    del env[k]
                    del env_original[k]
            # Restore all original values & empty backup...
            env.update(env_original)
            env_original.clear()

def env_remove(key: str):
    """ Remove an environment variable
    """
    global env_original
    env = os.environ
    if 'env_original' not in globals():
        env_original = {}
    if not key or type(key) is not str:
        raise ValueError("Missing or invalid key, str type required")
    if key in env:
        # Pre-existing unmodified value, save to backup
        if key not in env_original:
            env_original.update({key: env.get(key)})
        # New value that was added by env_set(), remove backup
        elif env_original.get(key) is None:
            del env_original[key]
        del env[key]
