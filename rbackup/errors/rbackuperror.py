class RBackupError(Exception):
    """ Parent class of all RBackup errors
    """
    def __init__(self, message=None, *, errors=None):
        super().__init__(message)
        self.message = message
        self.errors = errors or []
