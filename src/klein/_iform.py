class ValidationError(Exception):
    """
    A L{ValidationError} is raised by L{Field.extractValue}.
    """

    def __init__(self, message: object) -> None:
        """
        Initialize a L{ValidationError} with a message to show to the user.
        """
        super().__init__(message)
        self.message = message


class ValueAbsent(ValidationError):
    """
    A value was required but none was supplied.
    """
