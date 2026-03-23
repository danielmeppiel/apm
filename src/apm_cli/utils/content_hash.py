"""Deterministic SHA-256 content hashing for package integrity verification."""

import hashlib
from pathlib import Path
from typing import Optional

# Directories excluded from hashing (not relevant to package content)
_EXCLUDED_DIRS = {".git", "__pycache__"}

# Well-known hash for empty/missing packages
_EMPTY_HASH = "sha256:" + hashlib.sha256(b"").hexdigest()


def compute_package_hash(package_path: Path) -> str:
    """Compute a deterministic SHA-256 hash of a package's file tree.

    The hash is computed over sorted file paths and their contents,
    making it independent of filesystem ordering and metadata (timestamps,
    permissions).

    Args:
        package_path: Root directory of the installed package.

    Returns:
        Hash string in format ``"sha256:<hex_digest>"``.
    """
    if not package_path.is_dir():
        return _EMPTY_HASH

    hasher = hashlib.sha256()
    file_count = 0

    # Collect all regular files, skipping excluded dirs and symlinks
    regular_files: list[Path] = []
    for item in package_path.rglob("*"):
        # Skip symlinks
        if item.is_symlink():
            continue
        # Skip excluded directories and their contents
        rel = item.relative_to(package_path)
        if any(part in _EXCLUDED_DIRS for part in rel.parts):
            continue
        if item.is_file():
            regular_files.append(rel)

    # Sort lexicographically by POSIX path for determinism
    regular_files.sort(key=lambda p: p.as_posix())

    for rel_path in regular_files:
        # Hash the relative path then the file contents
        hasher.update(rel_path.as_posix().encode("utf-8"))
        hasher.update((package_path / rel_path).read_bytes())
        file_count += 1

    if file_count == 0:
        return _EMPTY_HASH

    return f"sha256:{hasher.hexdigest()}"


def verify_package_hash(package_path: Path, expected_hash: str) -> bool:
    """Verify a package's content matches the expected hash.

    Args:
        package_path: Root directory of the installed package.
        expected_hash: Expected hash string (e.g., ``"sha256:abc123..."``).

    Returns:
        True if hash matches, False if mismatch.
    """
    actual = compute_package_hash(package_path)
    return actual == expected_hash
