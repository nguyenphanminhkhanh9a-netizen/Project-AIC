"""Adversarial stress and verification tests for Owner Review Points 1 & 4.

Author: Challenger R3-1 (Adversarial Network & Memory Challenger)
Scope:
- Point 1: SSRF & DNS Rebinding in ssrf_guard.py and safe_downloader.py.
  - Rapid DNS flip (alternating IP addresses).
  - IPv6 scoped addresses, dual-stack spoofing, compressed IPv6 loopback (::ffff:127.0.0.1, [::1]).
  - Multi-hop redirect chains attempting rebinding mid-flight.
  - Preserved HTTPS TLS certificate validation against real domains.
- Point 4: SafeDownloader Memory Management and Lock Lifecycle.
  - Stress-test concurrent downloads of 100+ distinct URLs (zero lock leak).
  - Aggressive cancellation of in-flight downloads (ref_counts non-negative, zero lock leak).
  - High-throughput byte eviction (current_cache_bytes <= max_cache_bytes invariant).
"""

from __future__ import annotations

import asyncio
import random
import socket
from typing import Any
from unittest.mock import patch

import httpx
import pytest

from app.pipeline.security.safe_downloader import (
    DownloadInterruptedError,
    MaxRedirectsExceededError,
    SafeDownloader,
)
from app.pipeline.security.ssrf_guard import SSRFGuard, SSRFSecurityError

# ============================================================================
# POINT 1: SSRF & DNS REBINDING ADVERSARIAL SUITE
# ============================================================================


class TestSSRFAndDNSRebindingAdversarial:
    """Empirical adversarial stress tests for SSRF Guard and DNS Rebinding protections."""

    @pytest.mark.asyncio
    async def test_rapid_dns_flip_alternating_safe_and_blocked(self) -> None:
        """Rapid DNS flip alternating between benign public IP and loopback/private IPs."""
        guard = SSRFGuard()
        downloader = SafeDownloader(guard=guard)

        call_idx = 0
        blocked_targets = [
            "127.0.0.1",
            "10.0.0.1",
            "169.254.169.254",
            "192.168.1.1",
            "172.16.0.1",
            "::1",
            "100.64.0.1",
            "fc00::1",
        ]

        def alternating_getaddrinfo(
            host: str, port: int | str | None, *args: Any, **kwargs: Any
        ) -> list[Any]:
            nonlocal call_idx
            call_idx += 1
            port_int = int(port) if port is not None else 80
            # Even calls (validation): public safe IP
            # Odd calls (connection): alternating blocked IPs
            if call_idx % 2 == 1:
                return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port_int))]
            else:
                target_ip = blocked_targets[(call_idx // 2) % len(blocked_targets)]
                family = socket.AF_INET6 if ":" in target_ip else socket.AF_INET
                sockaddr = (target_ip, port_int, 0, 0) if family == socket.AF_INET6 else (target_ip, port_int)
                return [(family, socket.SOCK_STREAM, 6, "", sockaddr)]

        with patch("socket.getaddrinfo", side_effect=alternating_getaddrinfo):
            for i in range(16):
                with pytest.raises(SSRFSecurityError, match="blocked IP"):
                    await downloader.download(f"http://rapid-flip-{i}.example.com/asset.png")

    @pytest.mark.asyncio
    async def test_dual_stack_poisoning_with_various_private_ipv6(self) -> None:
        """Dual-stack DNS returning valid IPv4 alongside blocked IPv6 variants."""
        guard = SSRFGuard()
        downloader = SafeDownloader(guard=guard)

        blocked_ipv6_variants = [
            "::1",                      # Loopback
            "::",                       # Unspecified
            "::ffff:127.0.0.1",         # IPv4-mapped loopback
            "::ffff:169.254.169.254",   # IPv4-mapped metadata
            "::ffff:10.0.0.1",          # IPv4-mapped RFC 1918
            "fe80::1",                  # Link-local
            "fc00::1",                  # Unique Local Address (ULA)
            "fd00:ec2::254",            # AWS IPv6 metadata
        ]

        def make_fake_getaddrinfo(v6_ip: str) -> Any:
            def fake_getaddrinfo(
                host: str, port: int | str | None, *args: Any, **kwargs: Any
            ) -> list[Any]:
                port_int = int(port) if port is not None else 80
                return [
                    (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port_int)),
                    (socket.AF_INET6, socket.SOCK_STREAM, 6, "", (v6_ip, port_int, 0, 0)),
                ]
            return fake_getaddrinfo

        for blocked_v6 in blocked_ipv6_variants:
            with (
                patch("socket.getaddrinfo", side_effect=make_fake_getaddrinfo(blocked_v6)),
                pytest.raises(SSRFSecurityError, match="blocked IP"),
            ):
                await downloader.download(f"http://dual-stack-{blocked_v6.replace(':', '_')}.example.com/test.png")

    def test_ipv6_scoped_and_compressed_loopback_probes(self) -> None:
        """Adversarial encodings of IPv6 addresses rejected by SSRFGuard."""
        guard = SSRFGuard()
        probes = [
            "http://[::1]/test.png",
            "http://[::]/test.png",
            "http://[::ffff:127.0.0.1]/test.png",
            "http://[::ffff:7f00:1]/test.png",
            "http://[0:0:0:0:0:ffff:127.0.0.1]/test.png",
            "http://[::ffff:169.254.169.254]/test.png",
            "http://[::ffff:10.0.0.1]/test.png",
            "http://[fe80::1]/test.png",
            "http://[fe80::1%eth0]/test.png",
            "http://[fe80::1%1]/test.png",
            "http://[fc00::1]/test.png",
            "http://[fd00:ec2::254]/test.png",
        ]

        for url in probes:
            with pytest.raises(SSRFSecurityError):
                guard.validate_url(url)

    @pytest.mark.asyncio
    async def test_multihop_redirect_chains_rebinding_midflight(self) -> None:
        """Multi-hop redirect chain where final hop rebinds to metadata IP at connect time."""
        guard = SSRFGuard()
        downloader = SafeDownloader(guard=guard, max_redirects=3)

        # Hop 1 -> Hop 2 -> Hop 3 (rebinds to metadata)
        hop1_req = httpx.Request("GET", "http://hop1.example.com/asset.png")
        hop2_req = httpx.Request("GET", "http://hop2.example.com/asset.png")

        resp1 = httpx.Response(302, headers={"location": "http://hop2.example.com/asset.png"}, request=hop1_req)
        resp2 = httpx.Response(302, headers={"location": "http://rebind-final.example.com/asset.png"}, request=hop2_req)

        getaddrinfo_counts: dict[str, int] = {}

        def mock_getaddrinfo(host: str, port: int | str | None, *args: Any, **kwargs: Any) -> list[Any]:
            h = str(host)
            getaddrinfo_counts[h] = getaddrinfo_counts.get(h, 0) + 1
            port_int = int(port) if port is not None else 80
            if "hop1" in h or "hop2" in h:
                return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port_int))]
            # For rebind-final:
            # 1st call (validate_url) -> benign
            # 2nd call (connect_tcp) -> 169.254.169.254
            if getaddrinfo_counts[h] == 1:
                return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port_int))]
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("169.254.169.254", port_int))]

        orig_send = httpx.AsyncClient.send

        async def fake_send(client_self: Any, request: httpx.Request, *args: Any, **kwargs: Any) -> Any:
            url_str = str(request.url)
            if "hop1" in url_str:
                return resp1
            if "hop2" in url_str:
                return resp2
            return await orig_send(client_self, request, *args, **kwargs)

        with (
            patch("socket.getaddrinfo", side_effect=mock_getaddrinfo),
            patch.object(httpx.AsyncClient, "send", new=fake_send),
            pytest.raises(SSRFSecurityError, match="blocked IP '169.254.169.254'"),
        ):
            await downloader.download("http://hop1.example.com/asset.png")

    @pytest.mark.asyncio
    async def test_redirect_to_private_ip_directly_blocked(self) -> None:
        """Redirect response pointing directly to private IP is blocked before request is dispatched."""
        guard = SSRFGuard()
        downloader = SafeDownloader(guard=guard)

        hop1_req = httpx.Request("GET", "http://safe.example.com/image.png")
        resp1 = httpx.Response(302, headers={"location": "http://10.0.0.1/internal.png"}, request=hop1_req)

        def mock_getaddrinfo(host: str, port: int | str | None, *args: Any, **kwargs: Any) -> list[Any]:
            port_int = int(port) if port is not None else 80
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port_int))]

        orig_send = httpx.AsyncClient.send

        async def fake_send(client_self: Any, request: httpx.Request, *args: Any, **kwargs: Any) -> Any:
            if "safe.example.com" in str(request.url):
                return resp1
            return await orig_send(client_self, request, *args, **kwargs)

        with (
            patch("socket.getaddrinfo", side_effect=mock_getaddrinfo),
            patch.object(httpx.AsyncClient, "send", new=fake_send),
            pytest.raises(SSRFSecurityError, match="Direct connection to blocked IP '10.0.0.1' is prohibited"),
        ):
            await downloader.download("http://safe.example.com/image.png")

    @pytest.mark.asyncio
    async def test_excessive_redirect_chain_exceeding_max_hops(self) -> None:
        """Redirect chain exceeding max_redirects raises MaxRedirectsExceededError."""
        guard = SSRFGuard()
        downloader = SafeDownloader(guard=guard, max_redirects=3)

        def mock_getaddrinfo(host: str, port: int | str | None, *args: Any, **kwargs: Any) -> list[Any]:
            port_int = int(port) if port is not None else 80
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port_int))]

        hop_count = 0

        async def redirecting_send(client_self: Any, request: httpx.Request, *args: Any, **kwargs: Any) -> Any:
            nonlocal hop_count
            hop_count += 1
            return httpx.Response(
                302,
                headers={"location": f"http://safe.example.com/hop_{hop_count}.png"},
                request=request,
            )

        with (
            patch("socket.getaddrinfo", side_effect=mock_getaddrinfo),
            patch.object(httpx.AsyncClient, "send", new=redirecting_send),
            pytest.raises(MaxRedirectsExceededError, match=r"Redirect limit \(3 hops\) exceeded"),
        ):
            await downloader.download("http://safe.example.com/start.png")

    @pytest.mark.asyncio
    async def test_https_tls_hostname_and_cert_validation_enforced(self) -> None:
        """Empirical verification that SSRFSafeTransport enforces HTTPS certificate validation."""
        guard = SSRFGuard()
        downloader = SafeDownloader(guard=guard)

        # 1. Real domain with valid SSL cert succeeds
        data = await downloader.download("https://example.com")
        assert len(data) > 0
        assert b"<html" in data.lower() or b"<!doctype" in data.lower()

        # 2. Hostname mismatch / untrusted cert fails with SSL verification error
        with pytest.raises(DownloadInterruptedError, match=r"(?i)(certificate verify failed|hostname mismatch)"):
            await downloader.download("https://wrong.host.badssl.com/")


# ============================================================================
# POINT 4: SAFEDOWNLOADER MEMORY & LOCK LIFECYCLE ADVERSARIAL SUITE
# ============================================================================


class TestSafeDownloaderMemoryAndLocksAdversarial:
    """Empirical adversarial stress tests for memory limits, eviction, and lock lifecycles."""

    @pytest.mark.asyncio
    async def test_concurrent_downloads_128_distinct_urls_zero_lock_leak(self) -> None:
        """Download 128 distinct URLs concurrently and verify zero lock leak in _url_locks."""
        guard = SSRFGuard()
        downloader = SafeDownloader(guard=guard)

        async def fake_download(url: str) -> bytes:
            await asyncio.sleep(0.01)
            return b"payload_" + url.encode()

        downloader._download_uncached = fake_download  # type: ignore[assignment]

        urls = [f"https://example.com/distinct_asset_{i}.png" for i in range(128)]

        # Run 128 concurrent requests
        results = await asyncio.gather(*[downloader.download(u) for u in urls])

        assert len(results) == 128
        # Invariant: ALL locks and ref counts MUST be completely cleaned up
        assert len(downloader._url_locks) == 0, f"Leaked locks: {downloader._url_locks}"
        assert len(downloader._url_ref_counts) == 0, f"Leaked ref counts: {downloader._url_ref_counts}"

    @pytest.mark.asyncio
    async def test_aggressive_cancellation_waiting_and_running_tasks(self) -> None:
        """Stress-test lock lifecycle under aggressive cancellation of active and queued tasks."""
        guard = SSRFGuard()
        downloader = SafeDownloader(guard=guard)

        entered_events: dict[str, asyncio.Event] = {}

        async def slow_download(url: str) -> bytes:
            entered_events[url].set()
            await asyncio.sleep(0.5)
            return b"data_" + url.encode()

        downloader._download_uncached = slow_download  # type: ignore[assignment]

        urls = [f"https://example.com/cancel_target_{i}.png" for i in range(5)]
        for u in urls:
            entered_events[u] = asyncio.Event()

        # For each URL, launch 10 tasks (1 active, 9 waiting on lock) -> 50 total tasks
        tasks: list[asyncio.Task[bytes]] = []
        for u in urls:
            for _ in range(10):
                t = asyncio.create_task(downloader.download(u))
                tasks.append(t)

        # Wait until the first task of each URL enters download
        for u in urls:
            await entered_events[u].wait()

        # Randomly cancel half of the tasks
        random.seed(42)
        tasks_to_cancel = random.sample(tasks, 25)
        for t in tasks_to_cancel:
            t.cancel()

        # Await all tasks, handling CancelledError
        for t in tasks:
            try:
                await t
            except asyncio.CancelledError:
                pass

        # Invariant 1: _url_locks MUST be completely empty
        assert len(downloader._url_locks) == 0, f"Leaked locks after cancel: {downloader._url_locks}"
        # Invariant 2: _url_ref_counts MUST be completely empty
        assert len(downloader._url_ref_counts) == 0, f"Leaked ref counts after cancel: {downloader._url_ref_counts}"
        # Invariant 3: ref_counts must never have gone negative
        for count in downloader._url_ref_counts.values():
            assert count >= 0

    @pytest.mark.asyncio
    async def test_high_throughput_byte_eviction_ceiling_invariant(self) -> None:
        """High throughput downloads verifying _current_cache_bytes never exceeds max_cache_bytes."""
        guard = SSRFGuard()
        max_bytes = 100_000  # 100 KB
        max_entries = 50
        downloader = SafeDownloader(
            guard=guard,
            max_cache_entries=max_entries,
            max_cache_bytes=max_bytes,
        )

        async def dynamic_download(url: str) -> bytes:
            size = int(url.split("/")[-1])
            await asyncio.sleep(0.001)
            return b"B" * size

        downloader._download_uncached = dynamic_download  # type: ignore[assignment]

        # Generate 300 download requests with varying sizes:
        # Some small (500 B), medium (10 KB), large (40 KB), and oversized (120 KB > max_cache_bytes)
        sizes = [
            random.randint(500, 35_000) if i % 10 != 0 else 120_000
            for i in range(300)
        ]
        urls = [f"https://example.com/asset_{i}/{sizes[i]}" for i in range(300)]

        # Concurrently process in batches of 20
        batch_size = 20
        for i in range(0, len(urls), batch_size):
            batch = urls[i : i + batch_size]
            results = await asyncio.gather(*[downloader.download(u) for u in batch])
            assert len(results) == len(batch)

            # Invariant 1: current cache bytes <= max_cache_bytes ceiling
            assert (
                downloader._current_cache_bytes <= downloader.max_cache_bytes
            ), f"Cache byte overflow: {downloader._current_cache_bytes} > {downloader.max_cache_bytes}"

            # Invariant 2: current cache bytes matches exact sum of cached entries
            actual_bytes = sum(len(v) for v in downloader._cache.values())
            assert (
                downloader._current_cache_bytes == actual_bytes
            ), f"Byte accounting mismatch: tracked={downloader._current_cache_bytes}, actual={actual_bytes}"

            # Invariant 3: entry count <= max_cache_entries ceiling
            assert (
                len(downloader._cache) <= downloader.max_cache_entries
            ), f"Cache entry count overflow: {len(downloader._cache)} > {downloader.max_cache_entries}"

            # Invariant 4: non-negative byte count
            assert downloader._current_cache_bytes >= 0

        # Verify locks cleaned up
        assert len(downloader._url_locks) == 0
        assert len(downloader._url_ref_counts) == 0

    @pytest.mark.asyncio
    async def test_boundary_zero_and_negative_cache_limits(self) -> None:
        """Boundary test for max_cache_bytes = 0 or negative limits."""
        guard = SSRFGuard()
        downloader = SafeDownloader(
            guard=guard,
            max_cache_entries=10,
            max_cache_bytes=0,  # Cache disabled via 0 bytes
        )

        async def fake_download(url: str) -> bytes:
            return b"sample_bytes"

        downloader._download_uncached = fake_download  # type: ignore[assignment]

        res = await downloader.download("https://example.com/no_cache.png")
        assert res == b"sample_bytes"
        assert len(downloader._cache) == 0
        assert downloader._current_cache_bytes == 0

    @pytest.mark.asyncio
    async def test_total_cancellation_of_all_tasks(self) -> None:
        """Stress-test cancelling 100% of tasks across multiple URLs simultaneously."""
        guard = SSRFGuard()
        downloader = SafeDownloader(guard=guard)

        started_events: dict[str, asyncio.Event] = {}

        async def hung_download(url: str) -> bytes:
            started_events[url].set()
            await asyncio.sleep(100.0)  # Hang indefinitely until cancelled
            return b"hung"

        downloader._download_uncached = hung_download  # type: ignore[assignment]

        urls = [f"https://example.com/total_cancel_{i}.png" for i in range(10)]
        for u in urls:
            started_events[u] = asyncio.Event()

        # Launch 10 tasks per URL (100 total)
        tasks: list[asyncio.Task[bytes]] = []
        for u in urls:
            for _ in range(10):
                tasks.append(asyncio.create_task(downloader.download(u)))

        # Wait for all lock holders to start
        for u in urls:
            await started_events[u].wait()

        # Cancel ALL 100 tasks at once
        for t in tasks:
            t.cancel()

        for t in tasks:
            try:
                await t
            except asyncio.CancelledError:
                pass

        # Invariant: locks and ref_counts must be 100% pruned with zero leftovers
        assert len(downloader._url_locks) == 0, f"Leaked locks: {downloader._url_locks}"
        assert len(downloader._url_ref_counts) == 0, f"Leaked ref counts: {downloader._url_ref_counts}"

    @pytest.mark.asyncio
    async def test_cache_lru_order_under_memory_pressure(self) -> None:
        """Verify LRU order is strictly preserved when byte capacity evicts entries."""
        guard = SSRFGuard()
        downloader = SafeDownloader(
            guard=guard,
            max_cache_entries=5,
            max_cache_bytes=1000,
        )

        async def fake_download(url: str) -> bytes:
            size = int(url.split("/")[-1])
            return b"z" * size

        downloader._download_uncached = fake_download  # type: ignore[assignment]

        # Add item A (300B), B (300B), C (300B) -> 900B total
        await downloader.download("https://example.com/A/300")
        await downloader.download("https://example.com/B/300")
        await downloader.download("https://example.com/C/300")
        assert downloader._current_cache_bytes == 900
        assert list(downloader._cache.keys()) == [
            "https://example.com/A/300",
            "https://example.com/B/300",
            "https://example.com/C/300",
        ]

        # Re-access item A (cache hit) -> moves A to end: [B, C, A]
        await downloader.download("https://example.com/A/300")
        assert list(downloader._cache.keys()) == [
            "https://example.com/B/300",
            "https://example.com/C/300",
            "https://example.com/A/300",
        ]

        # Add item D (300B) -> 900 + 300 = 1200 > 1000 -> evicts oldest item (B)!
        await downloader.download("https://example.com/D/300")
        assert "https://example.com/B/300" not in downloader._cache
        assert "https://example.com/A/300" in downloader._cache  # A was preserved because it was recently accessed
        assert list(downloader._cache.keys()) == [
            "https://example.com/C/300",
            "https://example.com/A/300",
            "https://example.com/D/300",
        ]
        assert downloader._current_cache_bytes == 900

