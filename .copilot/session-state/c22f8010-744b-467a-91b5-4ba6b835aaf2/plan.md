# Plan: Content Scanner Performance Optimizations

## Analysis

### Current Performance Profile

The scanner is called once per package during `apm install` (3 call sites — local, cached, fresh download). Each call scans **one package directory** via `install_path.rglob("*")`, not the entire `apm_modules/`.

**Measured benchmarks** (M3 Mac):
- `scan_text()` on 10KB clean file: **0.5ms** (~20 MB/s throughput)
- `scan_file()` with disk I/O: **0.53ms** per 10KB file
- `str.isascii()` on 13KB string: **<0.001ms** (essentially free — C-level)
- `content.split("\n")`: **0.017ms** for 500 lines
- Per-character `ord()` loop: **1.4ms** for 22KB (this is the bottleneck)
- `_CHAR_LOOKUP`: 156 entries, O(1) dict lookup

**Scaling projections**:
| Scenario | Files | Estimated Time | With `isascii()` fast-path |
|----------|-------|---------------|---------------------------|
| 10 packages × 10 files | 100 | ~50ms | ~5ms |
| 50 packages × 10 files | 500 | ~250ms | ~26ms |
| 200 packages × 10 files | 2000 | ~1000ms | ~102ms |

### Key Finding: The Python `for` Loop is the Bottleneck

The character-by-character Python loop (`for ch in line_text: ord(ch)`) dominates. The `_CHAR_LOOKUP` dict is tiny (156 entries) and the O(1) lookup is negligible. The bottleneck is purely the Python interpreter overhead of iterating every character.

**But**: `str.isascii()` runs at C speed and returns in <1μs for 13KB strings. Since **>90% of prompt files are pure ASCII**, we can skip the entire scan for those files — a ~10x speedup at scale.

### What's NOT a Problem

1. **Scan scope (all files vs only primitives)**: A typical package has 10-50 files. Even scanning all of them takes <10ms. Filtering to only `.md`/`.yml` would save microseconds, not milliseconds, and would miss hidden chars in other file types.
2. **`ScanFinding` allocations**: Clean files create zero `ScanFinding` objects. Only the empty list `[]` is allocated.
3. **Memory**: `read_text()` loads full file — fine for prompt files (<100KB each).
4. **`has_critical()` + `summarize()` double pass**: Both iterate the findings list (typically 0-3 items). Combined savings: nanoseconds.

### What IS Worth Fixing

1. **No `isascii()` fast-path**: Every file gets the full character loop even when it's pure ASCII. Free 10x win.
2. **No early termination on critical + not force**: When `force=False` (default), a single critical finding means we block the install. No point scanning remaining files in the package — we already have the answer.
3. **`has_critical()` + `summarize()` are trivially combinable**: Not a perf issue, but a KISS cleanup — one pass instead of two for no reason.

## Approach

Three surgical optimizations — all in the hot path, no architecture changes:

### O1: `isascii()` fast-path in `scan_text()` 
Add `if content.isascii(): return []` before the character loop. C-level check, <1μs, skips 90%+ of files entirely.

### O2: Early termination in `_pre_deploy_security_scan()`
When `force=False` and we find a critical, stop scanning more files. We already know the answer: block.

### O3: Combine `has_critical()` + `summarize()` into single pass
Replace two separate calls with one combined helper. Trivial KISS cleanup.

## Todos

- [ ] `perf-isascii-fast-path` — Add `content.isascii()` early return to `scan_text()` for ~10x speedup on ASCII files
- [ ] `perf-early-terminate` — Break file loop in `_pre_deploy_security_scan()` when critical found and not force
- [ ] `perf-combine-has-summarize` — Combine `has_critical()` + `summarize()` calls into single pass

## Rejected Optimizations

- **Scope rglob to only primitive subdirs**: Marginal gain (saves scanning README/LICENSE — <5 files), reduces security coverage, adds coupling to package layout.
- **Streaming/chunked file reading**: Prompt files are <100KB. `read_text()` is fine. Chunked reading adds complexity for zero practical benefit.
- **Caching scan results**: Packages are scanned once per install. No repeated scans to cache.
- **Parallel file scanning**: Python GIL prevents true parallelism. `multiprocessing` overhead would exceed scan time for <50 files.
