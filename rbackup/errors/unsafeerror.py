from .rbackuperror import RBackupError

class UnsafeError(RBackupError):
    """Usage:
    raise(UnsafeError(errors="Local backup root does not exist and needs to be created.  Use '--force'."))
    raise(UnsafeError(errors="Will not allow current directory (.) as destination without '--force'."))
    """
    def __init__(self, message=None, errors=None):
        errors = list(errors) if isinstance(errors, (list, set, tuple)) \
            else ([] if errors is None else [errors])
        self.errors = errors
        if not message:
            message = "-f / --force required for some actions deemed \"unsafe\""
        if errors:
            message += ':\n'
            for err in errors:
                message += err + '\n'
        super().__init__(message)
