#!/usr/bin/env python3
"""Benchmark: manifest-based collision detection and sync operations.

Simulates realistic scale to measure the impact of algorithmic optimizations:
- Optimization 1: Pre-normalized managed_files set (check_collision)
- Optimization 2: Pre-partitioned managed_files (sync_remove_files)

Usage:
    uv run python scripts/benchmark_manifest_ops.py
"""

import time
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Synthetic data — models a repo managing 50 packages × 5 files each = 250
# managed paths (the scale scenario from the review comment).
# ---------------------------------------------------------------------------

PREFIXES = [
    ".github/prompts/",
    ".github/agents/",
    ".claude/agents/",
    ".claude/commands/",
    ".github/skills/",
    ".github/hooks/",
]

PACKAGES = 50
FILES_PER_PACKAGE = 5
INTEGRATOR_TYPES = 6  # prompts, agents-gh, agents-cl, commands, skills, hooks


def build_managed_files(n_packages: int, files_per_pkg: int) -> set:
    """Generate a synthetic managed_files set."""
    paths = set()
    for i in range(n_packages):
        prefix = PREFIXES[i % len(PREFIXES)]
        for j in range(files_per_pkg):
            paths.add(f"{prefix}pkg-{i}-file-{j}.md")
    return paths


# ---------------------------------------------------------------------------
# OLD: check_collision rebuilds a normalized set on every call
# ---------------------------------------------------------------------------

def check_collision_OLD(rel_path: str, managed_files: set) -> bool:
    """Original O(M) per call — rebuilds normalized set."""
    if rel_path.replace("\\", "/") in {p.replace("\\", "/") for p in managed_files}:
        return False
    return True


# ---------------------------------------------------------------------------
# NEW: managed_files is pre-normalized — O(1) amortized lookup
# ---------------------------------------------------------------------------

def normalize_managed_files(managed_files: set) -> set:
    return {p.replace("\\", "/") for p in managed_files}


def check_collision_NEW(rel_path: str, managed_files_normalized: set) -> bool:
    """Optimized O(1) lookup against pre-normalized set."""
    if rel_path.replace("\\", "/") in managed_files_normalized:
        return False
    return True


# ---------------------------------------------------------------------------
# OLD: sync_remove_files scans all paths with startswith for each integrator
# ---------------------------------------------------------------------------

def sync_remove_old(managed_files: set, prefix: str) -> int:
    """Original: iterate full set, filter by prefix."""
    count = 0
    for rel_path in managed_files:
        normalized = rel_path.replace("\\", "/")
        if not normalized.startswith(prefix) or ".." in rel_path:
            continue
        count += 1  # simulate file operation
    return count


# ---------------------------------------------------------------------------
# NEW: pre-partitioned — each integrator receives only its own paths
# ---------------------------------------------------------------------------

def partition_managed_files(managed_files: set) -> dict:
    """Single-pass partition by prefix."""
    buckets = {p: set() for p in PREFIXES}
    for p in managed_files:
        for prefix in PREFIXES:
            if p.startswith(prefix):
                buckets[prefix].add(p)
                break
    return buckets


def sync_remove_new(bucket: set) -> int:
    """Optimized: iterate only matching paths (no prefix check needed)."""
    count = 0
    for rel_path in bucket:
        if ".." in rel_path:
            continue
        count += 1
    return count


# ---------------------------------------------------------------------------
# Benchmarks
# ---------------------------------------------------------------------------

def timeit(fn, *args, iterations: int = 1000) -> float:
    """Return total time in ms for *iterations* calls."""
    start = time.perf_counter()
    for _ in range(iterations):
        fn(*args)
    return (time.perf_counter() - start) * 1000


def run_benchmarks():
    print("=" * 72)
    print("APM Manifest Operations Benchmark")
    print("=" * 72)

    for scale_label, n_pkgs, n_files in [
        ("Current (10 pkgs × 5 files = 50 paths)", 10, 5),
        ("Growing (50 pkgs × 5 files = 250 paths)", 50, 5),
        ("Large monorepo (100 pkgs × 20 files = 2000 paths)", 100, 20),
    ]:
        managed = build_managed_files(n_pkgs, n_files)
        M = len(managed)
        print(f"\n{'─' * 72}")
        print(f"Scale: {scale_label}  (M={M})")
        print(f"{'─' * 72}")

        # -- Benchmark 1: check_collision ----------------------------------
        #
        # Simulate: P=n_pkgs packages × F=n_files files × I=6 integrators
        # Each call does one collision check.
        calls = n_pkgs * n_files * INTEGRATOR_TYPES
        test_path = f".github/prompts/pkg-0-file-0.md"

        old_time = timeit(check_collision_OLD, test_path, managed, iterations=calls)
        normalized = normalize_managed_files(managed)
        norm_time = timeit(normalize_managed_files, managed, iterations=1)
        new_time = norm_time + timeit(check_collision_NEW, test_path, normalized, iterations=calls)

        print(f"\n  check_collision ({calls:,} calls):")
        print(f"    OLD (set rebuild per call):  {old_time:>8.2f} ms")
        print(f"    NEW (pre-normalized O(1)):   {new_time:>8.2f} ms")
        speedup = old_time / new_time if new_time > 0 else float("inf")
        print(f"    Speedup:                     {speedup:>8.1f}×")

        # -- Benchmark 2: sync_remove_files --------------------------------
        #
        # Simulate uninstall: 6 integrators, each scanning full M paths.
        sync_prefixes = PREFIXES
        iters = 100

        # OLD: 6 calls, each scanning full set
        old_sync = 0.0
        for _ in range(iters):
            t0 = time.perf_counter()
            for prefix in sync_prefixes:
                sync_remove_old(managed, prefix)
            old_sync += (time.perf_counter() - t0) * 1000

        # NEW: 1 partition pass + 6 calls over subset
        new_sync = 0.0
        for _ in range(iters):
            t0 = time.perf_counter()
            buckets = partition_managed_files(managed)
            for prefix in sync_prefixes:
                sync_remove_new(buckets[prefix])
            new_sync += (time.perf_counter() - t0) * 1000

        print(f"\n  sync_remove_files ({iters} uninstall cycles × 6 integrators):")
        print(f"    OLD (6× full-set scan):      {old_sync:>8.2f} ms")
        print(f"    NEW (pre-partitioned):       {new_sync:>8.2f} ms")
        speedup2 = old_sync / new_sync if new_sync > 0 else float("inf")
        print(f"    Speedup:                     {speedup2:>8.1f}×")

    print(f"\n{'=' * 72}")
    print("Done.")


if __name__ == "__main__":
    run_benchmarks()
