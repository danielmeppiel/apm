# Performance Baseline — Issue #171

Measured on `perf/171-deep-dependency-optimization` branch using `tests/benchmarks/run_baseline.py`.

**Environment:** macOS, Python 3.12, Apple Silicon (M-series), 5-run median.

## Results

| Benchmark | Baseline (ms) | Optimized (ms) | Speedup | Fix |
|---|--:|--:|--:|---|
| **Primitive conflict detection** | | | | |
| `primitive_add_unique_100` | 0.36 | 0.14 | 2.6× | Dict index O(1) lookup |
| `primitive_add_unique_500` | 5.57 | 0.85 | **6.5×** | Dict index O(1) lookup |
| `primitive_add_unique_1000` | 21.94 | 1.57 | **14.0×** | Dict index O(1) lookup |
| `primitive_conflict_50pct_100` | 0.26 | 0.16 | 1.6× | Dict index O(1) lookup |
| `primitive_conflict_50pct_500` | 3.06 | 0.83 | 3.7× | Dict index O(1) lookup |
| `primitive_conflict_50pct_1000` | 11.49 | 1.72 | **6.7×** | Dict index O(1) lookup |
| **Depth-indexed lookups** | | | | |
| `depth_lookup_50x5` | 0.01 | <0.01 | ~∞ | Pre-computed depth index |
| `depth_lookup_100x10` | 0.03 | <0.01 | ~∞ | Pre-computed depth index |
| `depth_lookup_500x10` | 0.14 | <0.01 | **14×+** | Pre-computed depth index |
| **Cycle detection** | | | | |
| `cycle_detect_chain_20` | 0.02 | 0.02 | 1.0× | Set companion (small N) |
| `cycle_detect_chain_50` | 0.05 | 0.04 | 1.3× | Set companion |
| `cycle_detect_chain_100` | 0.16 | 0.09 | 1.8× | Set companion |
| **Flatten** | | | | |
| `flatten_50x5` | 0.04 | 0.03 | 1.3× | Depth index benefit |
| `flatten_100x10` | 0.12 | 0.05 | 2.4× | Depth index benefit |
| `flatten_500x10` | 0.40 | 0.25 | 1.6× | Depth index benefit |
| **YAML parse caching** | | | | |
| `from_apm_yml_x10` | 1.35 | 0.29 | **4.7×** | Module-level cache |
| `from_apm_yml_x50` | 6.68 | 1.51 | **4.4×** | Module-level cache |
| **Parallel downloads (Phase 4)** | | | | |
| `sequential_10x50ms` | 533.79 | 534.68 | 1.0× | Baseline for comparison |
| `parallel_4w_10x50ms` | 164.85 | 163.59 | ~1.0× | ThreadPoolExecutor overhead |

## Analysis

### Highest-impact fixes (Phase 2 — Data Structures)
- **Primitive conflict detection** showed the clearest O(m²) → O(m) improvement. At 1000 primitives, the Dict-based index is **14× faster** — the quadratic growth curve is eliminated.
- **Depth lookups** dropped to near-zero with the pre-computed `_nodes_by_depth` Dict, eliminating repeated full-scan iterations during `flatten_dependencies()`.

### Caching (Phase 3)
- **`from_apm_yml()`** cache reduces 50-call repeated parses from 6.68ms → 1.51ms (4.4×). The first call still hits disk; subsequent calls are Dict lookups. Real-world CLI operations with 20-50 repeated parses will see significant I/O savings.
- **`read_constitution()`** and **`get_config()`** caching not benchmarked here (require file I/O fixtures) but follow the same pattern: 1 disk read per process instead of 3-10.

### Parallel downloads (Phase 4)
- The `sequential_10x50ms` vs `parallel_4w_10x50ms` benchmark demonstrates the ThreadPoolExecutor pattern: 10 simulated 50ms I/O tasks complete in ~164ms with 4 workers vs ~534ms sequentially — a **3.3× wall-clock speedup**. This closely matches the theoretical ceiling of `ceil(10/4) × 50ms = 150ms`.
- In real-world `apm install`, the speedup depends on network conditions and package count. With 10 packages averaging 5s each: sequential ≈ 50s, parallel (4 workers) ≈ 15s.
- Git sparse-checkout for subdirectory packages reduces bandwidth further by downloading only the target subdirectory instead of the full repository.

### Cycle detection
- Modest improvement (1.8× at 100 nodes). The `Set` companion for O(1) `in` checks matters more at deeper trees (100+ depth) than the chain lengths tested. The primary benefit is preventing degenerate performance on adversarial dependency graphs.

### Flatten
- Up to 2.4× improvement at 100 packages — combines depth-index O(1) lookups with pre-allocated lists.

## Notes
- Phases 2-3 benchmarks are synthetic (in-memory). Real-world improvement depends on package count and tree shape.
- Phase 4 parallel download benchmark uses simulated sleep to isolate ThreadPoolExecutor overhead from network variability. Real `apm install` speedup will be higher due to actual I/O latency.
- Phase 5 (rate-limit retries, skip-if-exists) improvements are not measurable via synthetic benchmarks — they affect resilience under API throttling and skip unnecessary re-downloads.
- Run benchmarks: `uv run python tests/benchmarks/run_baseline.py`
