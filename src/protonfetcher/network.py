"""Network client implementation for ProtonFetcher."""

import logging
import urllib.error
import urllib.request

from .common import Headers, HttpResponse
from .exceptions import NetworkError

logger = logging.getLogger(__name__)


class NetworkClient:
    """Concrete implementation of NetworkClientProtocol using urllib.

    Redirects are followed automatically. HTTP error statuses (4xx/5xx)
    are returned as HttpResponse; connection-level failures raise
    NetworkError.
    """

    def __init__(self, timeout: int = 30) -> None:
        self.timeout = timeout

    def _request(self, url: str, method: str, headers: Headers | None) -> HttpResponse:
        req = urllib.request.Request(url, method=method, headers=headers or {})
        try:
            response = urllib.request.urlopen(req, timeout=self.timeout)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace") if method == "GET" else ""
            return HttpResponse(
                status=e.code,
                headers=_lowercase_headers(e.headers),
                body=body,
                final_url=url,
            )
        except urllib.error.URLError as e:
            raise NetworkError(f"Network request to {url} failed: {e.reason}") from e
        except (TimeoutError, OSError) as e:
            raise NetworkError(f"Network request to {url} failed: {e}") from e

        with response:
            body = response.read().decode("utf-8", errors="replace")
            return HttpResponse(
                status=response.status,
                headers=_lowercase_headers(response.headers),
                body=body,
                final_url=response.url,
            )

    def get(self, url: str, headers: Headers | None = None) -> HttpResponse:
        """Perform an HTTP GET request (redirects are followed)."""
        return self._request(url, "GET", headers)

    def head(self, url: str, headers: Headers | None = None) -> HttpResponse:
        """Perform an HTTP HEAD request (redirects are followed)."""
        return self._request(url, "HEAD", headers)


def _lowercase_headers(message) -> dict[str, str]:
    """Convert an email.message.Message to a dict with lowercase keys."""
    if message is None:
        return {}
    return {key.lower(): value for key, value in message.items()}
