"""Adversarial security and payload tests by Challenger 1.

Phase 0.5A Automatic Asset Processing Pipeline Security Probes.
Covers SSRFGuard, ImageSanitizer, and SafeDownloader under adversarial inputs.
"""

from __future__ import annotations

import io
import socket
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from PIL import Image, PngImagePlugin

from app.pipeline.security.safe_downloader import (
    DownloadInterruptedError,
    MaxRedirectsExceededError,
    OversizedPayloadError,
    SafeDownloader,
)
from app.pipeline.security.sanitizer import (
    CorruptedImageError,
    ImageSanitizer,
    InvalidImageHeaderError,
    SecurityViolationError,
)
from app.pipeline.security.ssrf_guard import SSRFGuard, SSRFSecurityError


class TestSSRFGuardAdversarial:
    """Adversarial probes against SSRFGuard IP encodings, schemes, and resolution."""

    def test_ssrf_ip_encodings_blocked(self) -> None:
        """Adversarial encodings of localhost and cloud metadata are safely rejected."""
        guard = SSRFGuard()
        adversarial_urls = [
            "http://127.0.0.1/",
            "http://127.0.0.2/",
            "http://127.1/",
            "http://127.0.1/",
            "http://0.0.0.0/",
            "http://0/",
            "http://2130706433/",
            "http://017700000001/",
            "http://0177.0.0.1/",
            "http://0x7f000001/",
            "http://0x7f.0.0.1/",
            "http://169.254.169.254/",
            "http://2852039166/",
            "http://0xa9fea9fe/",
            "http://[::1]/",
            "http://[::]/",
            "http://[0:0:0:0:0:0:0:1]/",
            "http://[0000::0001]/",
            "http://[::ffff:127.0.0.1]/",
            "http://[::ffff:7f00:1]/",
            "http://[::ffff:a9fe:a9fe]/",
            "http://[fd00:ec2::254]/",
            "http://[fe80::1]/",
            "http://[fc00::1]/",
            "http://10.0.0.1/",
            "http://172.16.0.1/",
            "http://192.168.1.1/",
            "http://100.64.0.1/",
            "http://localhost/",
            "http://localhost:8000/",
        ]
        for url in adversarial_urls:
            with pytest.raises(SSRFSecurityError):
                guard.validate_url(url)

    def test_ssrf_multi_ip_dual_stack_blocked(self) -> None:
        """If DNS returns dual-stack / multi-IP where ANY address is private, it must block."""
        guard = SSRFGuard()
        # Mock dual-stack DNS: IPv4 public, IPv6 loopback
        mock_addr_info = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 80)),
            (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("::1", 80)),
        ]
        with (
            patch("socket.getaddrinfo", return_value=mock_addr_info),
            pytest.raises(SSRFSecurityError, match="blocked IP '::1'"),
        ):
            guard.validate_url("http://mixed-dns.example.com/")

    def test_ssrf_aws_ipv6_metadata_blocked(self) -> None:
        """Cloud metadata IPv6 [fd00:ec2::254] in DNS resolution must be blocked."""
        guard = SSRFGuard()
        mock_addr_info = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 80)),
            (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("fd00:ec2::254", 80)),
        ]
        with (
            patch("socket.getaddrinfo", return_value=mock_addr_info),
            pytest.raises(SSRFSecurityError, match="blocked IP 'fd00:ec2::254'"),
        ):
            guard.validate_url("http://aws-meta.example.com/")

    def test_ssrf_scheme_bypasses_rejected(self) -> None:
        """Non-HTTP schemes and embedded credentials must be rejected."""
        guard = SSRFGuard()
        dangerous = [
            "file:///etc/shadow",
            "ftp://anonymous@example.com/",
            "gopher://127.0.0.1:70/",
            "data:image/png;base64,iVBORw0KGgo=",
            "javascript:alert(1)",
            "ws://example.com/socket",
            "wss://example.com/socket",
            "blob:http://example.com/123",
            "ldap://127.0.0.1:389/",
            "http://admin:secret@example.com/image.png",
            "http://",
            "https://",
            "",
            "   ",
        ]
        for url in dangerous:
            with pytest.raises(SSRFSecurityError):
                guard.validate_url(url)

    def test_ssrf_security_error_is_value_error_subclass_vulnerability(self) -> None:
        """Verifies SSRFSecurityError inherits from ValueError and is NOT swallowed in validate_url."""
        assert issubclass(SSRFSecurityError, ValueError)

        guard = SSRFGuard()
        # When socket.getaddrinfo is mocked to return a public IP, validating http://127.0.0.1/
        # must block at the IP literal stage and raise SSRFSecurityError rather than swallowing it.
        mock_public_dns = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 80))]
        with (
            patch("socket.getaddrinfo", return_value=mock_public_dns),
            pytest.raises(
                SSRFSecurityError, match="Direct connection to blocked IP '127.0.0.1' is prohibited."
            ),
        ):
            guard.validate_url("http://127.0.0.1/")


class TestRedirectAndDownloaderAdversarial:
    """Adversarial probes against SafeDownloader redirects, timeouts, and limits."""

    @pytest.mark.asyncio
    async def test_redirect_to_file_scheme_blocked_on_hop(self) -> None:
        """Open redirect targeting file:/// scheme must be intercepted."""
        guard = SSRFGuard()
        downloader = SafeDownloader(guard=guard, max_redirects=3)
        mock_resp = AsyncMock(
            status_code=302,
            headers={"Location": "file:///etc/passwd"},
            aclose=AsyncMock(),
        )
        with (
            patch("httpx.AsyncClient.send", return_value=mock_resp),
            patch.object(guard, "validate_url", side_effect=[None, SSRFSecurityError("Disallowed scheme")]),
            pytest.raises(SSRFSecurityError, match="Disallowed scheme"),
        ):
            await downloader.download("https://example.com/start")

    @pytest.mark.asyncio
    async def test_redirect_to_private_ip_blocked(self) -> None:
        """Redirect to private IP on second hop must be blocked."""
        guard = SSRFGuard()
        downloader = SafeDownloader(guard=guard, max_redirects=3)
        mock_resp = AsyncMock(
            status_code=302,
            headers={"Location": "http://10.0.0.1/internal.png"},
            aclose=AsyncMock(),
        )
        with (
            patch("httpx.AsyncClient.send", return_value=mock_resp),
            patch.object(guard, "validate_url", side_effect=[None, SSRFSecurityError("Blocked IP '10.0.0.1'")]),
            pytest.raises(SSRFSecurityError, match="Blocked IP '10.0.0.1'"),
        ):
            await downloader.download("https://example.com/redirect_to_private")

    @pytest.mark.asyncio
    async def test_redirect_exact_boundary_conditions(self) -> None:
        """Exactly 3 redirects succeed, 4 redirects raise MaxRedirectsExceededError."""
        guard = SSRFGuard()
        downloader = SafeDownloader(guard=guard, max_redirects=3)
        fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32

        # 3 redirects + 1 final 200 response = 4 total requests
        hop_count = 0

        async def send_3hops(request: httpx.Request, **kwargs: object) -> AsyncMock:
            nonlocal hop_count
            hop_count += 1
            resp = AsyncMock()
            resp.aclose = AsyncMock()
            if hop_count <= 3:
                resp.status_code = 302
                resp.headers = {"Location": f"https://example.com/hop{hop_count}"}
            else:
                resp.status_code = 200
                resp.headers = {"Content-Length": str(len(fake_png))}

                async def fake_iter(chunk_size: int = 65536) -> AsyncGenerator[bytes, None]:
                    yield fake_png

                resp.aiter_bytes = fake_iter
            return resp

        with patch("httpx.AsyncClient.send", side_effect=send_3hops), patch.object(guard, "validate_url"):
            data = await downloader.download("https://example.com/test_3hops")
            assert data == fake_png
            assert hop_count == 4

        # 4 redirects must exceed limit
        hop_count = 0

        async def send_4hops(request: httpx.Request, **kwargs: object) -> AsyncMock:
            nonlocal hop_count
            hop_count += 1
            resp = AsyncMock()
            resp.aclose = AsyncMock()
            resp.status_code = 302
            resp.headers = {"Location": f"https://example.com/hop{hop_count}"}
            return resp

        with (
            patch("httpx.AsyncClient.send", side_effect=send_4hops),
            patch.object(guard, "validate_url"),
            pytest.raises(MaxRedirectsExceededError),
        ):
            await downloader.download("https://example.com/test_4hops")

    @pytest.mark.asyncio
    async def test_declared_content_length_oversized_abort(self) -> None:
        """Declared Content-Length > 15MB must abort before chunk streaming."""
        guard = SSRFGuard()
        limit = 15 * 1024 * 1024
        downloader = SafeDownloader(guard=guard, max_size_bytes=limit)

        mock_resp = AsyncMock(
            status_code=200,
            headers={"Content-Length": str(limit + 1)},
            aclose=AsyncMock(),
        )
        with (
            patch("httpx.AsyncClient.send", return_value=mock_resp),
            patch.object(guard, "validate_url"),
            pytest.raises(OversizedPayloadError, match="exceeds limit"),
        ):
            await downloader.download("https://example.com/oversized_header")
        assert mock_resp.aclose.called

    @pytest.mark.asyncio
    async def test_chunked_streaming_oversized_abort(self) -> None:
        """Chunked transfer without Content-Length exceeding 15MB aborts mid-stream."""
        guard = SSRFGuard()
        downloader = SafeDownloader(guard=guard, max_size_bytes=1024 * 1024)  # 1MB for test

        mock_resp = AsyncMock(status_code=200, headers={}, aclose=AsyncMock())

        async def fake_stream(chunk_size: int = 65536) -> AsyncGenerator[bytes, None]:
            yield b"X" * (600 * 1024)
            yield b"X" * (600 * 1024)

        mock_resp.aiter_bytes = fake_stream

        with (
            patch("httpx.AsyncClient.send", return_value=mock_resp),
            patch.object(guard, "validate_url"),
            pytest.raises(OversizedPayloadError, match="exceeded maximum allowed limit"),
        ):
            await downloader.download("https://example.com/stream_overflow")
        assert mock_resp.aclose.called

    @pytest.mark.asyncio
    async def test_midstream_drop_cleans_up(self) -> None:
        """Abrupt connection drop during streaming raises DownloadInterruptedError and closes response."""
        guard = SSRFGuard()
        downloader = SafeDownloader(guard=guard)

        mock_resp = AsyncMock(status_code=200, headers={}, aclose=AsyncMock())

        async def broken_stream(chunk_size: int = 65536) -> AsyncGenerator[bytes, None]:
            yield b"partial"
            raise httpx.RemoteProtocolError("Connection reset by peer")

        mock_resp.aiter_bytes = broken_stream

        with (
            patch("httpx.AsyncClient.send", return_value=mock_resp),
            patch.object(guard, "validate_url"),
            pytest.raises(DownloadInterruptedError, match="Connection abruptly dropped"),
        ):
            await downloader.download("https://example.com/broken_stream")
        assert mock_resp.aclose.called


class TestImageSanitizerAdversarial:
    """Adversarial probes against ImageSanitizer magic bytes, polyglots, and bombs."""

    def test_magic_bytes_strict_rejection(self) -> None:
        """Invalid headers and disallowed file formats are rejected."""
        sanitizer = ImageSanitizer()
        invalids = [
            b"",
            b"\x89",
            b"\x89PNG\r\n\x1a",  # 7 bytes
            b"\x89PNG\r\n\x1a\x00",  # bad terminator
            b"\xff\xd8",  # 2 bytes
            b"\xff\xd8\x00",  # bad marker
            b"RIFF\x00\x00\x00\x00AVI ",
            b"GIF89a\x01\x00\x01\x00",
            b"BM\x00\x00\x00\x00",
            b"<!DOCTYPE html>",
            b"PK\x03\x04",  # Zip file
        ]
        for header in invalids:
            with pytest.raises(InvalidImageHeaderError):
                sanitizer.sniff_magic_bytes(header)

    def test_truncated_streams_fail_verification(self) -> None:
        """Truncated image streams raise CorruptedImageError."""
        sanitizer = ImageSanitizer()
        truncated = [
            b"\x89PNG\r\n\x1a\n",  # header only
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00",
            b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00",
        ]
        for payload in truncated:
            with pytest.raises(CorruptedImageError):
                sanitizer.validate_raw_bytes(payload)

    def test_polyglot_script_injection_stripped(self) -> None:
        """Embedded JavaScript / PHP in ancillary chunks or appended to IEND are completely stripped."""
        sanitizer = ImageSanitizer()
        img = Image.new("RGBA", (32, 32), (0, 255, 0, 255))
        png_info = PngImagePlugin.PngInfo()
        png_info.add_text("XSS", "<script>alert(1)</script>")
        png_info.add_text("RCE", "<?php phpinfo(); ?>")

        buf = io.BytesIO()
        img.save(buf, format="PNG", pnginfo=png_info)
        polyglot = buf.getvalue() + b"\n<script>alert('trailing')</script>"

        # Verify raw payload contains injected scripts
        assert b"<script>" in polyglot
        assert b"<?php" in polyglot

        # Sanitize image
        clean_img = sanitizer.sanitize_image(polyglot)
        clean_png = sanitizer.to_png_bytes(clean_img)

        # In output PNG, no scripts must exist
        assert b"<script>" not in clean_png
        assert b"<?php" not in clean_png

    def test_decompression_bomb_2x_pixel_rejection(self) -> None:
        """Decompression bombs exceeding 2 * max_pixels raise SecurityViolationError and restore global state."""
        limit_pixels = 500 * 500  # 250,000 pixels
        sanitizer = ImageSanitizer(max_pixels=limit_pixels)

        # Create 1000x1000 image (1,000,000 pixels > 2 * 250,000)
        huge_img = Image.new("L", (1000, 1000), 200)
        buf = io.BytesIO()
        huge_img.save(buf, format="PNG")
        bomb_bytes = buf.getvalue()

        orig_pixels = Image.MAX_IMAGE_PIXELS

        with pytest.raises(SecurityViolationError, match="Decompression bomb"):
            sanitizer.validate_raw_bytes(bomb_bytes)

        # Global PIL limit must be safely restored
        assert Image.MAX_IMAGE_PIXELS == orig_pixels

        with pytest.raises(SecurityViolationError, match="Decompression bomb"):
            sanitizer.sanitize_image(bomb_bytes)

        assert Image.MAX_IMAGE_PIXELS == orig_pixels

    def test_decompression_bomb_warning_bypass_vulnerability(self) -> None:
        """Verifies images between max_pixels and 2 * max_pixels are rejected across the entire range."""
        limit_pixels = 500 * 500  # 250,000 pixels
        sanitizer = ImageSanitizer(max_pixels=limit_pixels)

        # Create 600x600 image (360,000 pixels: 250k < pixels <= 500k)
        bomb_img = Image.new("L", (600, 600), 128)
        buf = io.BytesIO()
        bomb_img.save(buf, format="PNG")
        data = buf.getvalue()

        # Both validate_raw_bytes and sanitize_image must raise SecurityViolationError
        with pytest.raises(SecurityViolationError, match="Decompression bomb"):
            sanitizer.validate_raw_bytes(data)

        with pytest.raises(SecurityViolationError, match="Decompression bomb"):
            sanitizer.sanitize_image(data)
