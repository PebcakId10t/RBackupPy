from .rbackuperror import RBackupError

class JobError(RBackupError):
    """ Raised if there is an error while running a backup job
    """
    def __init__(self, message="Job failed", *, errors=None, exitcode=None):
        if exitcode:
            message += f" with exit code {exitcode}"
        if not errors:
            errors = []
        else:
            message += ':\n'
            for e in errors:
                message += str(e) + '\n'
        super().__init__(message, errors=errors)
        self.message = message
        self.errors = errors
        self.exitcode = exitcode


class JobSuccess(RBackupError):
    """ Job succeeded (raised like an exception, used for flow control/logging)
    """
    def __init__(self, message="Job appears to have succeeded", *, errors=None, exitcode=None):
        if exitcode:
            message += f" (exit code {exitcode})."
        if isinstance(errors, str):
            # raise JobSuccess(errors="There was nothing to transfer") weirdness
            message += '  ' + errors
        elif isinstance(errors, list):
            message += '\n'
            for e in errors:
                message += str(e) + '\n'
        super().__init__(message, errors=errors)
        self.message = message
        self.errors = errors
        self.exitcode = exitcode
