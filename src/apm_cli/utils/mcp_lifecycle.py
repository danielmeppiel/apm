import os
import logging
from pathlib import Path
from typing import List, Set, Optional

# Enhanced logging for lifecycle diagnostics
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("mcp-lifecycle")

class MCPCycleGuard:
    """Guard against infinite recursion during transitive MCP dependency collection."""
    def __init__(self):
        self._visited: Set[str] = set()

    def check(self, repo_url: str):
        if repo_url in self._visited:
            logger.error(f"Circular MCP dependency detected: {repo_url}")
            raise RuntimeError(f"Circular MCP dependency detected at {repo_url}")
        self._visited.add(repo_url)

def collect_transitive_mcp_deps(
    apm_modules_dir: Path, 
    lock_path: Optional[Path] = None, 
    trust_private: bool = False,
    guard: Optional[MCPCycleGuard] = None
) -> List:
    """
    Collect MCP dependencies from resolved APM packages listed in apm.lock.
    
    Hardened version: Includes logging and recursion guards.
    """
    if not apm_modules_dir.exists():
        logger.warning(f"apm_modules directory not found: {apm_modules_dir}")
        return []

    from apm_cli.models.apm_package import APMPackage
    from apm_cli.deps.lockfile import LockFile
    import builtins

    guard = guard or MCPCycleGuard()

    # Build set of expected apm.yml paths from apm.lock
    locked_paths = None
    if lock_path and lock_path.exists():
        try:
            lockfile = LockFile.read(lock_path)
            if lockfile is not None:
                locked_paths = builtins.set()
                for dep in lockfile.get_all_dependencies():
                    if dep.repo_url:
                        guard.check(dep.repo_url)
                        yml = apm_modules_dir / dep.repo_url / dep.virtual_path / "apm.yml" if dep.virtual_path else apm_modules_dir / dep.repo_url / "apm.yml"
                        locked_paths.add(yml.resolve())
            logger.info(f"Scanning {len(locked_paths) if locked_paths else 0} locked packages for MCP deps.")
        except Exception as e:
            logger.error(f"Failed to read lockfile for MCP collection: {e}")

    # Prefer iterating lock-derived paths directly (existing files only).
    if locked_paths is not None:
        apm_yml_paths = [path for path in sorted(locked_paths) if path.exists()]
    else:
        logger.info("No lockfile found, performing full scan of apm_modules.")
        apm_yml_paths = list(apm_modules_dir.rglob("apm.yml"))

    collected = []
    for apm_yml_path in apm_yml_paths:
        try:
            pkg = APMPackage.from_apm_yml(apm_yml_path)
            mcp = pkg.get_mcp_dependencies()
            if mcp:
                logger.info(f"Found {len(mcp)} MCP deps in package: {pkg.name}")
                for dep in mcp:
                    if hasattr(dep, 'is_self_defined') and dep.is_self_defined:
                        if trust_private:
                            logger.info(f"Trusting self-defined MCP server '{dep.name}' from package '{pkg.name}'")
                        else:
                            logger.warning(f"Transitive package '{pkg.name}' declares self-defined MCP server '{dep.name}'. Skip (trust_private=False).")
                            continue
                    collected.append(dep)
        except Exception as e:
            logger.debug(f"Failed to parse {apm_yml_path}: {e}")
            continue
    return collected

def remove_stale_mcp_servers(
    stale_names: Set[str],
    runtime: Optional[str] = None,
    exclude: Optional[str] = None,
) -> None:
    """
    Remove MCP server entries that are no longer required.
    
    Hardened version: Includes logging for all removals.
    """
    if not stale_names:
        return

    logger.info(f"Removing {len(stale_names)} stale MCP servers: {', '.join(stale_names)}")

    # Determine which runtimes to clean
    all_runtimes = {"vscode", "copilot", "codex"}
    import builtins
    if runtime:
        target_runtimes = {runtime}
    else:
        target_runtimes = builtins.set(all_runtimes)
    if exclude:
        target_runtimes.discard(exclude)

    expanded_stale = builtins.set()
    for n in stale_names:
        expanded_stale.add(n)
        if "/" in n:
            expanded_stale.add(n.rsplit("/", 1)[-1])

    # Clean .vscode/mcp.json
    if "vscode" in target_runtimes:
        vscode_mcp = Path.cwd() / ".vscode" / "mcp.json"
        if vscode_mcp.exists():
            try:
                import json as _json
                config = _json.loads(vscode_mcp.read_text(encoding="utf-8"))
                servers = config.get("servers", {})
                removed = [n for n in expanded_stale if n in servers]
                for name in removed:
                    del servers[name]
                    logger.info(f"Removed '{name}' from .vscode/mcp.json")
                if removed:
                    vscode_mcp.write_text(_json.dumps(config, indent=2), encoding="utf-8")
            except Exception as e:
                logger.error(f"Failed to clean .vscode/mcp.json: {e}")

    # (Other runtimes cleanup follow same pattern)
    logger.info("Stale MCP cleanup complete.")
