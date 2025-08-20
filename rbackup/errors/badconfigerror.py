from .rbackuperror import RBackupError

class BadConfigError(RBackupError):
    """ Raised if one or more issues are detected with the config file.
    """
    def __init__(self, message="Bad config.\n", *, errors=None):
        if not errors:
            errors = []
        for e in errors:
            message += e + '\n'
        super().__init__(message, errors=errors)
        self.message = message
        self.errors = errors
