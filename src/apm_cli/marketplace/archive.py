"""Download and safely extract Agent Skills archive packages (.tar.gz / .zip).

Handles ``type: "archive"`` skill entries from the Agent Skills discovery RFC.
All extraction paths are validated against the destination directory to prevent
path traversal, and total uncompressed size is bounded to prevent decompression
bombs.
"""

import io
import os
import tarfile
import zipfile
from typing import List

import requests

_MAX_UNCOMPRESSED_BYTES = 512 * 1024 * 1024  # 512 MB


class ArchiveError(Exception):
    """Raised when an archive cannot be downloaded or extracted safely."""


def _check_archive_member(member_path: str) -> None:
    """Validate a single archive member path.

    Raises:
        ArchiveError: If the path is absolute (including Windows drive-letter
            and UNC forms), contains path traversal sequences (``..``), or
            contains a null byte.
    """
    if "\x00" in member_path:
        raise ArchiveError(f"Archive member path contains null byte: {member_path!r}")
    # os.path.isabs catches Unix-style absolute paths.  Windows drive-letter
    # paths (e.g. "C:\..." or "C:/...") and UNC paths ("\\server\share") are
    # not caught by os.path.isabs on non-Windows hosts, so check explicitly.
    if os.path.isabs(member_path):
        raise ArchiveError(f"Archive member has absolute path: {member_path!r}")
    forward = member_path.replace("\\", "/")
    if forward.startswith("//") or (
        len(forward) >= 2 and forward[1] == ":" and forward[0].isalpha()
    ):
        raise ArchiveError(f"Archive member has absolute path: {member_path!r}")
    normalized = os.path.normpath(member_path)
    if normalized.startswith(".."):
        raise ArchiveError(
            f"Archive member path traversal detected: {member_path!r}"
        )
    parts = forward.split("/")
    if ".." in parts:
        raise ArchiveError(
            f"Archive member path traversal detected: {member_path!r}"
        )


def _detect_archive_format(content_type: str, url: str) -> str:
    """Detect archive format from Content-Type header or URL extension.

    Content-Type takes priority over the URL when both are provided.

    Returns:
        ``"tar.gz"`` or ``"zip"``.

    Raises:
        ArchiveError: When the format cannot be determined.
    """
    ct = content_type.lower().split(";")[0].strip()
    if ct in ("application/gzip", "application/x-gzip", "application/x-tar"):
        return "tar.gz"
    if ct in ("application/zip", "application/x-zip-compressed"):
        return "zip"

    lower_url = url.lower().split("?")[0]
    if lower_url.endswith(".tar.gz") or lower_url.endswith(".tgz"):
        return "tar.gz"
    if lower_url.endswith(".zip"):
        return "zip"

    raise ArchiveError(
        f"Cannot determine archive format from Content-Type={content_type!r} "
        f"and URL={url!r}"
    )


def _extract_tar_gz(data: bytes, dest_dir: str) -> List[str]:
    """Extract a tar.gz archive to *dest_dir* with safety checks.

    Args:
        data: Raw archive bytes.
        dest_dir: Directory to extract into (must already exist).

    Returns:
        List of relative paths extracted.

    Raises:
        ArchiveError: On path traversal, symlink escape, or decompression bomb.
    """
    extracted: List[str] = []
    total_size = 0

    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
            for member in tf.getmembers():
                if member.isdir():
                    continue
                if member.issym() or member.islnk():
                    raise ArchiveError(
                        f"Symlinks and hard links are not supported: {member.name!r}"
                    )
                _check_archive_member(member.name)

                total_size += member.size
                if total_size > _MAX_UNCOMPRESSED_BYTES:
                    raise ArchiveError(
                        f"Archive exceeds size limit of {_MAX_UNCOMPRESSED_BYTES} bytes "
                        f"(decompression bomb guard)"
                    )

                dest_path = os.path.realpath(os.path.join(dest_dir, member.name))
                real_dest = os.path.realpath(dest_dir)
                if not dest_path.startswith(real_dest + os.sep) and dest_path != real_dest:
                    raise ArchiveError(
                        f"Archive member would extract outside destination: {member.name!r}"
                    )

                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                with tf.extractfile(member) as src, open(dest_path, "wb") as dst:
                    dst.write(src.read())
                extracted.append(member.name)
    except (tarfile.TarError, KeyError) as exc:
        raise ArchiveError(f"Failed to read tar.gz archive: {exc}") from exc

    return extracted


def _extract_zip(data: bytes, dest_dir: str) -> List[str]:
    """Extract a zip archive to *dest_dir* with safety checks.

    Args:
        data: Raw archive bytes.
        dest_dir: Directory to extract into (must already exist).

    Returns:
        List of relative paths extracted.

    Raises:
        ArchiveError: On path traversal, absolute paths, or decompression bomb.
    """
    extracted: List[str] = []
    total_size = 0

    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            for info in zf.infolist():
                if info.filename.endswith("/"):
                    continue
                _check_archive_member(info.filename)

                total_size += info.file_size
                if total_size > _MAX_UNCOMPRESSED_BYTES:
                    raise ArchiveError(
                        f"Archive exceeds size limit of {_MAX_UNCOMPRESSED_BYTES} bytes "
                        f"(decompression bomb guard)"
                    )

                dest_path = os.path.realpath(os.path.join(dest_dir, info.filename))
                real_dest = os.path.realpath(dest_dir)
                if not dest_path.startswith(real_dest + os.sep) and dest_path != real_dest:
                    raise ArchiveError(
                        f"Archive member would extract outside destination: {info.filename!r}"
                    )

                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                with zf.open(info) as src, open(dest_path, "wb") as dst:
                    dst.write(src.read())
                extracted.append(info.filename)
    except zipfile.BadZipFile as exc:
        raise ArchiveError(f"Failed to read zip archive: {exc}") from exc

    return extracted


def download_and_extract_archive(url: str, dest_dir: str) -> List[str]:
    """Download an archive from *url* and extract it to *dest_dir*.

    Detects format from Content-Type header or URL extension. Applies full
    safety checks (path traversal, decompression bomb).

    Args:
        url: HTTPS URL of the archive.
        dest_dir: Directory to extract into (created if it does not exist).

    Returns:
        List of relative paths extracted.

    Raises:
        ArchiveError: On download failure, unrecognised format, or unsafe content.
    """
    try:
        resp = requests.get(url, headers={"User-Agent": "apm-cli"}, timeout=60)
        resp.raise_for_status()
    except requests.exceptions.RequestException as exc:
        raise ArchiveError(f"Failed to download archive from {url!r}: {exc}") from exc

    content_type = resp.headers.get("Content-Type", "")
    fmt = _detect_archive_format(content_type, url)

    os.makedirs(dest_dir, exist_ok=True)

    if fmt == "tar.gz":
        return _extract_tar_gz(resp.content, dest_dir)
    return _extract_zip(resp.content, dest_dir)
