"""Exception classes for ProtonFetcher."""


class ProtonFetcherError(Exception):
    """Base exception for ProtonFetcher operations."""


# For backward compatibility with existing code
FetchError = ProtonFetcherError


class NetworkError(ProtonFetcherError):
    """Raised when network operations fail."""


class ExtractionError(ProtonFetcherError):
    """Raised when archive extraction fails."""


class LinkManagementError(ProtonFetcherError):
    """Raised when link management operations fail."""


class MultiLinkManagementError(ProtonFetcherError, ExceptionGroup):
    """Raised when multiple link management operations fail."""
