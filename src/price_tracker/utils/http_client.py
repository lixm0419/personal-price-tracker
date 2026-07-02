import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from urllib.parse import urlparse
from urllib.request import Request, urlopen

LOGGER = logging.getLogger(__name__)

Transport = Callable[[str, float, Mapping[str, str]], str]
DEFAULT_USER_AGENT = (
    "PersonalPriceTracker/0.1 "
    "(compatible; personal-use price monitoring)"
)


class HttpClientError(RuntimeError):
    """HTML could not be downloaded after the configured attempts."""


@dataclass(slots=True)
class HttpClient:
    """Reusable text HTTP client with simple retry and transport hooks."""

    timeout: float = 15.0
    retries: int = 1
    user_agent: str = DEFAULT_USER_AGENT
    headers: dict[str, str] = field(default_factory=dict)
    transports: dict[str, Transport] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.timeout <= 0:
            raise ValueError("timeout must be greater than zero")
        if self.retries < 0:
            raise ValueError("retries cannot be negative")

    def fetch(self, url: str) -> str:
        scheme = urlparse(url).scheme.lower()
        transport = self.transports.get(scheme, self._download_http)
        headers = {"User-Agent": self.user_agent, **self.headers}
        attempts = self.retries + 1
        for attempt in range(1, attempts + 1):
            try:
                return transport(url, self.timeout, headers)
            except Exception as exc:
                LOGGER.warning(
                    "Request failed for %s (attempt %d/%d): %s",
                    url,
                    attempt,
                    attempts,
                    exc,
                )
                if attempt == attempts:
                    raise HttpClientError(
                        f"Unable to download {url} after {attempts} attempt(s): "
                        f"{exc}"
                    ) from exc
        raise AssertionError("unreachable")

    @staticmethod
    def _download_http(
        url: str, timeout: float, headers: Mapping[str, str]
    ) -> str:
        scheme = urlparse(url).scheme.lower()
        if scheme not in {"http", "https"}:
            raise ValueError(f"Unsupported URL scheme: {scheme or '(missing)'}")
        request = Request(url, headers=dict(headers))
        with urlopen(request, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, errors="replace")
