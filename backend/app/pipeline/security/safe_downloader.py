"""Secure HTTP image downloader with anti-SSRF pre-checks, redirect guards, and streaming size limits.

Phase 0.5A Automatic Asset Processing Pipeline.
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from collections import OrderedDict
from collections.abc import AsyncGenerator, Iterable
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import urljoin

import httpcore
import httpx

from app.pipeline.security.sanitizer import ImageSanitizer
from app.pipeline.security.ssrf_guard import SSRFGuard, SSRFSecurityError


class SafeDownloaderError(Exception):
    """Base exception for safe downloader errors."""


class MaxRedirectsExceededError(SafeDownloaderError):
    """Raised when HTTP redirect chain exceeds maximum allowed hops."""


class OversizedPayloadError(SafeDownloaderError):
    """Raised when downloaded image exceeds maximum allowed byte limit."""


class DownloadTimeoutError(SafeDownloaderError):
    """Raised when socket connection or read exceeds timeout limit."""


class DownloadInterruptedError(SafeDownloaderError):
    """Raised when connection drops mid-stream or protocol error occurs."""


class SSRFSafeNetworkBackend(httpcore.AsyncNetworkBackend):
    """Custom HTTPCore network backend that enforces SSRF checks and pins IP connections."""

    def __init__(
        self,
        guard: SSRFGuard,
        backend: httpcore.AsyncNetworkBackend | None = None,
    ) -> None:
        self.guard = guard
        self._backend = backend or httpcore.AnyIOBackend()

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Iterable[httpcore.SOCKET_OPTION] | None = None,
    ) -> httpcore.AsyncNetworkStream:
        clean_host = host.strip("[]")
        try:
            ipaddress.ip_address(clean_host)
            is_ip = True
        except ValueError:
            is_ip = False

        if is_ip:
            if not self.guard.is_safe_ip(clean_host):
                raise SSRFSecurityError(
                    f"Direct connection to blocked IP '{clean_host}' is prohibited."
                )
            safe_ips = [clean_host]
        else:
            loop = asyncio.get_running_loop()
            try:
                addr_info = await loop.getaddrinfo(
                    host,
                    port,
                    family=socket.AF_UNSPEC,
                    type=socket.SOCK_STREAM,
                )
            except socket.gaierror as e:
                raise SSRFSecurityError(f"Failed to resolve hostname '{host}': {e}") from e

            if not addr_info:
                raise SSRFSecurityError(f"No IP address resolved for hostname '{host}'.")

            safe_ips = []
            for entry in addr_info:
                ip_str = str(entry[4][0])
                if not self.guard.is_safe_ip(ip_str):
                    raise SSRFSecurityError(
                        f"Hostname '{host}' resolved to blocked IP '{ip_str}'."
                    )
                safe_ips.append(ip_str)

        # Connect to validated safe IP literals (prevents OS-level DNS re-resolution)
        last_exc: Exception | None = None
        for ip in safe_ips:
            try:
                return await self._backend.connect_tcp(
                    host=ip,
                    port=port,
                    timeout=timeout,
                    local_address=local_address,
                    socket_options=socket_options,
                )
            except (httpcore.ConnectError, httpcore.ConnectTimeout, OSError) as exc:
                last_exc = exc

        if last_exc is not None:
            raise last_exc
        raise httpcore.ConnectError(f"Failed to connect to '{host}:{port}'.")

    async def connect_unix_socket(
        self,
        path: str,
        timeout: float | None = None,
        socket_options: Iterable[httpcore.SOCKET_OPTION] | None = None,
    ) -> httpcore.AsyncNetworkStream:
        return await self._backend.connect_unix_socket(
            path=path,
            timeout=timeout,
            socket_options=socket_options,
        )

    async def sleep(self, seconds: float) -> None:
        await self._backend.sleep(seconds)


class SSRFSafeTransport(httpx.AsyncHTTPTransport):
    """Async HTTP transport enforcing SSRF validation and IP connection pinning."""

    def __init__(self, guard: SSRFGuard, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._pool = httpcore.AsyncConnectionPool(
            ssl_context=self._pool._ssl_context,
            max_connections=self._pool._max_connections,
            max_keepalive_connections=self._pool._max_keepalive_connections,
            keepalive_expiry=self._pool._keepalive_expiry,
            http1=self._pool._http1,
            http2=self._pool._http2,
            network_backend=SSRFSafeNetworkBackend(guard=guard),
        )


class SafeDownloader:
    """Safely downloads remote images enforcing SSRF guards, redirect limits, and payload caps."""

    def __init__(
        self,
        guard: SSRFGuard | None = None,
        sanitizer: ImageSanitizer | None = None,
        max_size_bytes: int = 15 * 1024 * 1024,
        timeout_seconds: float = 10.0,
        connect_timeout_seconds: float = 5.0,
        max_redirects: int = 3,
        max_cache_entries: int = 64,
        max_cache_bytes: int = 64 * 1024 * 1024,
    ) -> None:
        self.guard = guard if guard is not None else SSRFGuard()
        self.sanitizer = sanitizer if sanitizer is not None else ImageSanitizer()
        self.max_size_bytes = max_size_bytes
        self.timeout_seconds = timeout_seconds
        self.connect_timeout_seconds = connect_timeout_seconds
        self.max_redirects = max_redirects
        self.max_cache_entries = max_cache_entries
        self.max_cache_bytes = max_cache_bytes
        self._url_locks: dict[str, asyncio.Lock] = {}
        self._url_ref_counts: dict[str, int] = {}
        self._cache: OrderedDict[str, bytes] = OrderedDict()
        self._current_cache_bytes: int = 0

    def _get_url_lock(self, url: str) -> asyncio.Lock:
        if url not in self._url_locks:
            self._url_locks[url] = asyncio.Lock()
        return self._url_locks[url]

    @asynccontextmanager
    async def _acquire_url_lock(self, url: str) -> AsyncGenerator[None, None]:
        if url not in self._url_locks:
            self._url_locks[url] = asyncio.Lock()
            self._url_ref_counts[url] = 0
        self._url_ref_counts[url] += 1
        lock = self._url_locks[url]

        try:
            async with lock:
                yield
        finally:
            self._url_ref_counts[url] -= 1
            if self._url_ref_counts[url] <= 0:
                self._url_locks.pop(url, None)
                self._url_ref_counts.pop(url, None)

    def _store_in_cache(self, url: str, data: bytes) -> None:
        data_len = len(data)
        if (
            self.max_cache_entries <= 0
            or self.max_cache_bytes <= 0
            or data_len > self.max_cache_bytes
        ):
            return

        if url in self._cache:
            old_bytes = self._cache.pop(url)
            self._current_cache_bytes -= len(old_bytes)

        # Evict oldest until incoming fits both count and byte constraints
        while self._cache and (
            len(self._cache) >= self.max_cache_entries
            or self._current_cache_bytes + data_len > self.max_cache_bytes
        ):
            _, evicted_bytes = self._cache.popitem(last=False)
            self._current_cache_bytes -= len(evicted_bytes)

        if (
            self._current_cache_bytes + data_len <= self.max_cache_bytes
            and len(self._cache) < self.max_cache_entries
        ):
            self._cache[url] = data
            self._current_cache_bytes += data_len
            self._cache.move_to_end(url)

    async def download(self, url: str) -> bytes:
        """Downloads an image from URL enforcing SSRF validation, redirects, and size caps.

        Uses in-flight locking to prevent duplicate concurrent downloads of identical URLs.
        """
        async with self._acquire_url_lock(url):
            if url in self._cache:
                self._cache.move_to_end(url)
                return self._cache[url]

            data = await self._download_uncached(url)
            self._store_in_cache(url, data)
            return data

    async def _download_uncached(self, start_url: str) -> bytes:
        current_url = start_url
        redirect_hops = 0

        timeout = httpx.Timeout(
            timeout=self.timeout_seconds,
            connect=self.connect_timeout_seconds,
        )

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            "Accept": "image/webp,image/png,image/jpeg,image/*;q=0.8",
        }

        transport = SSRFSafeTransport(guard=self.guard)
        async with httpx.AsyncClient(
            transport=transport,
            follow_redirects=False,
            timeout=timeout,
        ) as client:
            while True:
                # 1. Anti-SSRF check before every request/hop
                try:
                    self.guard.validate_url(current_url)
                except SSRFSecurityError as e:
                    raise SSRFSecurityError(
                        f"SSRF validation failed for URL '{current_url}': {e}"
                    ) from e

                try:
                    request = client.build_request("GET", current_url, headers=headers)
                    response = await client.send(request, stream=True)
                except httpx.ConnectTimeout as e:
                    raise DownloadTimeoutError(
                        f"Connection timed out connecting to '{current_url}'."
                    ) from e
                except httpx.ReadTimeout as e:
                    raise DownloadTimeoutError(
                        f"Socket read timed out reading from '{current_url}'."
                    ) from e
                except (httpx.RemoteProtocolError, httpx.TransportError) as e:
                    raise DownloadInterruptedError(
                        f"Connection interrupted while connecting to '{current_url}': {e}"
                    ) from e

                # 2. Check for HTTP redirects (301, 302, 303, 307, 308)
                if response.status_code in (301, 302, 303, 307, 308):
                    await response.aclose()
                    redirect_hops += 1
                    if redirect_hops > self.max_redirects:
                        raise MaxRedirectsExceededError(
                            f"Redirect limit ({self.max_redirects} hops) exceeded for '{start_url}'."
                        )

                    location = response.headers.get("Location")
                    if not location:
                        raise SafeDownloaderError(
                            f"Redirect response {response.status_code} missing Location header."
                        )

                    current_url = urljoin(current_url, location)
                    continue

                # 3. Check for HTTP errors
                if response.status_code != 200:
                    await response.aclose()
                    raise SafeDownloaderError(
                        f"HTTP download request failed with status {response.status_code}."
                    )

                # 4. Check Content-Length header ceiling
                content_length_str = response.headers.get("Content-Length")
                if content_length_str:
                    try:
                        content_length = int(content_length_str)
                        if content_length > self.max_size_bytes:
                            await response.aclose()
                            raise OversizedPayloadError(
                                f"Declared Content-Length ({content_length} bytes) "
                                f"exceeds limit ({self.max_size_bytes} bytes)."
                            )
                    except ValueError:
                        pass

                # 5. Stream byte chunks with strict cumulative size cap
                chunks: list[bytes] = []
                total_bytes = 0

                try:
                    async for chunk in response.aiter_bytes(chunk_size=65536):
                        total_bytes += len(chunk)
                        if total_bytes > self.max_size_bytes:
                            await response.aclose()
                            raise OversizedPayloadError(
                                f"Cumulative payload size ({total_bytes} bytes) "
                                f"exceeded maximum allowed limit ({self.max_size_bytes} bytes)."
                            )
                        chunks.append(chunk)
                except (httpx.RemoteProtocolError, httpx.TransportError) as e:
                    await response.aclose()
                    raise DownloadInterruptedError(
                        f"Connection abruptly dropped mid-stream: {e}"
                    ) from e
                except httpx.ReadTimeout as e:
                    await response.aclose()
                    raise DownloadTimeoutError(
                        f"Read timeout while streaming chunks from '{current_url}': {e}"
                    ) from e
                finally:
                    await response.aclose()

                data = b"".join(chunks)
                if not data:
                    raise SafeDownloaderError("Downloaded payload was empty.")

                return data
