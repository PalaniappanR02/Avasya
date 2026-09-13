class IngestionError(RuntimeError):
    """Raised when a dataset cannot be safely ingested."""


class ValidationError(IngestionError):
    """Raised when a dataset fails structural or value validation."""
