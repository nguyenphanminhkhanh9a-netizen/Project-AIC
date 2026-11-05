"""Suite 3: SafeDownloader and SSRFGuard security tests.

Phase 0.5A Automatic Asset Processing Pipeline.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.pipeline.security.safe_downloader import (
    DownloadTimeoutError,
    MaxRedirectsExceededError,
    OversizedPayloadError,
    SafeDownloader,
)
from app.pipeline.security.ssrf_guard import SSRFGuard, SSRFSecurityError


def test_ssrf_rejects_non_http_schemes() -> None:
    """Verifies that non-http/https URL schemes are blocked prior to connection."""
    guard = SSRFGuard()
    dangerous_urls = [
        "file:///etc/passwd",
        "file:///C:/Windows/system32/cmd.exe",
        "ftp://example.com/asset.png",
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAUA...",
        "gopher://127.0.0.1:70/",
        "javascript:alert(1)",
    ]
    for url in dangerous_urls:
        with pytest.raises(SSRFSecurityError):
            guard.validate_url(url)


def test_ssrf_blocks_private_and_loopback_ips() -> None:
    """Verifies that private, loopback, link-local, and cloud metadata IPs are rejected."""
    guard = SSRFGuard()
    blocked_ips = [
        "127.0.0.1",
        "127.0.0.2",
        "10.0.0.1",
        "172.16.0.1",
        "172.31.255.254",
        "192.168.1.1",
        "169.254.169.254",  # AWS/Azure metadata
        "100.64.0.1",       # Carrier-grade NAT
        "::1",
        "fe80::1",
        "fc00::1",
        "::ffff:127.0.0.1",
    ]
    for ip in blocked_ips:
        assert not guard.is_safe_ip(ip), f"IP {ip} should be rejected as unsafe"


def test_ssrf_blocks_direct_ip_urls() -> None:
    """Verifies direct IP URLs in private ranges fail validate_url."""
    guard = SSRFGuard()
    with pytest.raises(SSRFSecurityError):
        guard.validate_url("http://127.0.0.1:8000/image.png")
    with pytest.raises(SSRFSecurityError):
        guard.validate_url("http://169.254.169.254/latest/meta-data/")
    with pytest.raises(SSRFSecurityError):
        guard.validate_url("http://[::1]/secret.png")


def test_ssrf_blocks_urls_with_credentials() -> None:
    """Verifies URLs with embedded user:pass are rejected."""
    guard = SSRFGuard()
    with pytest.raises(SSRFSecurityError):
        guard.validate_url("http://user:password@example.com/img.png")


@pytest.mark.asyncio
async def test_redirect_hop_limit() -> None:
    """Verifies that redirect chains exceeding max_redirects raise MaxRedirectsExceededError."""
    guard = SSRFGuard()
    downloader = SafeDownloader(guard=guard, max_redirects=3)

    # Mock response returning 302 redirects continuously
    mock_response = AsyncMock()
    mock_response.status_code = 302
    mock_response.headers = {"Location": "https://example.com/next_hop"}
    mock_response.aclose = AsyncMock()

    with (
        patch("httpx.AsyncClient.send", return_value=mock_response),
        patch.object(guard, "validate_url"),  # Bypass DNS check for mock domain
        pytest.raises(MaxRedirectsExceededError),
    ):
        await downloader.download("https://example.com/start")


@pytest.mark.asyncio
async def test_ssrf_redirect_to_internal_metadata_blocked() -> None:
    """Verifies that a redirect to a blocked private IP is intercepted on hop 2."""
    guard = SSRFGuard()
    downloader = SafeDownloader(guard=guard, max_redirects=3)

    # First hop returns 302 pointing to cloud metadata
    mock_response = AsyncMock()
    mock_response.status_code = 302
    mock_response.headers = {"Location": "http://169.254.169.254/secret.png"}
    mock_response.aclose = AsyncMock()

    with (
        patch("httpx.AsyncClient.send", return_value=mock_response),
        patch.object(guard, "validate_url", side_effect=[None, SSRFSecurityError("Blocked IP")]),
        pytest.raises(SSRFSecurityError),
    ):
        await downloader.download("https://example.com/initial")


@pytest.mark.asyncio
async def test_streaming_size_limit_abort() -> None:
    """Verifies that downloads exceeding max_size_bytes abort with OversizedPayloadError."""
    guard = SSRFGuard()
    # 1KB limit for test
    downloader = SafeDownloader(guard=guard, max_size_bytes=1024)

    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.headers = {}
    mock_response.aclose = AsyncMock()

    # Stream yields chunks totaling 2KB
    async def fake_stream(chunk_size: int = 65536) -> AsyncGenerator[bytes, None]:
        yield b"x" * 600
        yield b"x" * 600

    mock_response.aiter_bytes = fake_stream

    with (
        patch("httpx.AsyncClient.send", return_value=mock_response),
        patch.object(guard, "validate_url"),
        pytest.raises(OversizedPayloadError),
    ):
        await downloader.download("https://example.com/huge.png")


@pytest.mark.asyncio
async def test_timeout_handling() -> None:
    """Verifies that ConnectTimeout or ReadTimeout raises DownloadTimeoutError."""
    guard = SSRFGuard()
    downloader = SafeDownloader(guard=guard, timeout_seconds=1.0)

    with (
        patch("httpx.AsyncClient.send", side_effect=httpx.ReadTimeout("Timeout")),
        patch.object(guard, "validate_url"),
        pytest.raises(DownloadTimeoutError),
    ):
        await downloader.download("https://example.com/slow.png")


@pytest.mark.asyncio
async def test_concurrent_download_deduplication() -> None:
    """Verifies in-flight locking downloads identical URL only once across concurrent coroutines."""
    guard = SSRFGuard()
    downloader = SafeDownloader(guard=guard)

    call_count = 0
    fake_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100

    async def fake_uncached(url: str) -> bytes:
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.02)
        return fake_bytes

    downloader._download_uncached = fake_uncached  # type: ignore[assignment]

    url = "https://example.com/shared_art.png"
    results = await asyncio.gather(*[downloader.download(url) for _ in range(5)])

    assert len(results) == 5
    assert all(r == fake_bytes for r in results)
    assert call_count == 1

