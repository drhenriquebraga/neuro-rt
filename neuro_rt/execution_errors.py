"""Fatal execution ownership errors must never be isolated as model failures."""


class ProcessTreeUnconfirmed(RuntimeError):
    """The owned process tree has not been confirmed stopped; keep its lease."""

    def __init__(self, message, *, process=None):
        super().__init__(message)
        self.process = process
