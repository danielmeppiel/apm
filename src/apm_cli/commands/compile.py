"""APM compile command."""

import sys
from pathlib import Path

import click

from ..compilation import AgentsCompiler, CompilationConfig
from ..primitives.discovery import discover_primitives
from ..utils.console import (
    STATUS_SYMBOLS,
    _rich_echo,
    _rich_error,
    _rich_info,
    _rich_panel,
    _rich_success,
    _rich_warning,
)
from ._helpers import (
    _atomic_write,
    _check_orphaned_packages,
    _get_console,
    _rich_blank_line,
)


def _display_validation_errors(errors):
    """Display validation errors in a Rich table with actionable feedback."""
    try:
        console = _get_console()
        if console:
            from rich.table import Table

            error_table = Table(
                title="[x] Primitive Validation Errors",
                show_header=True,
                header_style="bold red",
            )
            error_table.add_column("File", style="bold red", min_width=20)
            error_table.add_column("Error", style="white", min_width=30)
            error_table.add_column("Suggestion", style="yellow", min_width=25)

            for error in errors:
                file_path = str(error) if hasattr(error, "__str__") else "Unknown"
                # Extract file path from error string if it contains file info
                if ":" in file_path:
                    parts = file_path.split(":", 1)
                    file_name = parts[0] if len(parts) > 1 else "Unknown"
                    error_msg = parts[1].strip() if len(parts) > 1 else file_path
                else:
                    file_name = "Unknown"
                    error_msg = file_path

                # Provide actionable suggestions based on error type
                suggestion = _get_validation_suggestion(error_msg)
                error_table.add_row(file_name, error_msg, suggestion)

            console.print(error_table)
            return

    except (ImportError, NameError):
        pass

    # Fallback to simple text output
    _rich_error("Validation errors found:")
    for error in errors:
        click.echo(f"  [x] {error}")


def _get_validation_suggestion(error_msg):
    """Get actionable suggestions for validation errors."""
    if "Missing 'description'" in error_msg:
        return "Add 'description: Your description here' to frontmatter"
    elif "Missing 'applyTo'" in error_msg:
        return "Add 'applyTo: \"**/*.py\"' to frontmatter"
    elif "Empty content" in error_msg:
        return "Add markdown content below the frontmatter"
    else:
        return "Check primitive structure and frontmatter"


def _watch_mode(output, chatmode, no_links, dry_run):
    """Watch for changes in .apm/ directories and auto-recompile."""
    try:
        # Try to import watchdog for file system monitoring
        import time

        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer

        class APMFileHandler(FileSystemEventHandler):
            def __init__(self, output, chatmode, no_links, dry_run):
                self.output = output
                self.chatmode = chatmode
                self.no_links = no_links
                self.dry_run = dry_run
                self.last_compile = 0
                self.debounce_delay = 1.0  # 1 second debounce

            def on_modified(self, event):
                if event.is_directory:
                    return

                # Check if it's a relevant file
                if event.src_path.endswith(".md") or event.src_path.endswith("apm.yml"):

                    # Debounce rapid changes
                    current_time = time.time()
                    if current_time - self.last_compile < self.debounce_delay:
                        return

                    self.last_compile = current_time
                    self._recompile(event.src_path)

            def _recompile(self, changed_file):
                """Recompile after file change."""
                try:
                    _rich_info(f"File changed: {changed_file}", symbol="eyes")
                    _rich_info("Recompiling...", symbol="gear")

                    # Create configuration from apm.yml with overrides
                    config = CompilationConfig.from_apm_yml(
                        output_path=self.output if self.output != "AGENTS.md" else None,
                        chatmode=self.chatmode,
                        resolve_links=not self.no_links if self.no_links else None,
                        dry_run=self.dry_run,
                    )

                    # Create compiler and compile
                    compiler = AgentsCompiler(".")
                    result = compiler.compile(config)

                    if result.success:
                        if self.dry_run:
                            _rich_success(
                                "Recompilation successful (dry run)", symbol="sparkles"
                            )
                        else:
                            _rich_success(
                                f"Recompiled to {result.output_path}", symbol="sparkles"
                            )
                    else:
                        _rich_error("Recompilation failed")
                        for error in result.errors:
                            click.echo(f"  [x] {error}")

                except Exception as e:
                    _rich_error(f"Error during recompilation: {e}")

        # Set up file watching
        event_handler = APMFileHandler(output, chatmode, no_links, dry_run)
        observer = Observer()

        # Watch patterns for APM files
        watch_paths = []

        # Check for .apm directory
        if Path(".apm").exists():
            observer.schedule(event_handler, ".apm", recursive=True)
            watch_paths.append(".apm/")

        # Check for .github/instructions and agents/chatmodes
        if Path(".github/instructions").exists():
            observer.schedule(event_handler, ".github/instructions", recursive=True)
            watch_paths.append(".github/instructions/")

        # Watch .github/agents/ (new standard)
        if Path(".github/agents").exists():
            observer.schedule(event_handler, ".github/agents", recursive=True)
            watch_paths.append(".github/agents/")

        # Watch .github/chatmodes/ (legacy)
        if Path(".github/chatmodes").exists():
            observer.schedule(event_handler, ".github/chatmodes", recursive=True)
            watch_paths.append(".github/chatmodes/")

        # Watch apm.yml if it exists
        if Path("apm.yml").exists():
            observer.schedule(event_handler, ".", recursive=False)
            watch_paths.append("apm.yml")

        if not watch_paths:
            _rich_warning("No APM directories found to watch")
            _rich_info("Run 'apm init' to create an APM project")
            return

        # Start watching
        observer.start()
        _rich_info(
            f" Watching for changes in: {', '.join(watch_paths)}", symbol="eyes"
        )
        _rich_info("Press Ctrl+C to stop watching...", symbol="info")

        # Do initial compilation
        _rich_info("Performing initial compilation...", symbol="gear")

        config = CompilationConfig.from_apm_yml(
            output_path=output if output != "AGENTS.md" else None,
            chatmode=chatmode,
            resolve_links=not no_links if no_links else None,
            dry_run=dry_run,
        )

        compiler = AgentsCompiler(".")
        result = compiler.compile(config)

        if result.success:
            if dry_run:
                _rich_success(
                    "Initial compilation successful (dry run)", symbol="sparkles"
                )
            else:
                _rich_success(
                    f"Initial compilation complete: {result.output_path}",
                    symbol="sparkles",
                )
        else:
            _rich_error("Initial compilation failed")
            for error in result.errors:
                click.echo(f"  [x] {error}")

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
            _rich_info("Stopped watching for changes", symbol="info")

        observer.join()

    except ImportError:
        _rich_error("Watch mode requires the 'watchdog' library")
        _rich_info("Install it with: uv pip install watchdog")
        _rich_info(
            "Or reinstall APM: uv pip install -e . (from the apm directory)"
        )
        sys.exit(1)
    except Exception as e:
        _rich_error(f"Error in watch mode: {e}")
        sys.exit(1)


@click.command(help="Compile APM context into distributed AGENTS.md files")
@click.option(
    "--output",
    "-o",
    default="AGENTS.md",
    help="Output file path (for single-file mode)",
)
@click.option(
    "--target",
    "-t",
    type=click.Choice(["vscode", "agents", "claude", "opencode", "all"]),
    default=None,
    help="Target platform: vscode/agents (AGENTS.md), opencode (AGENTS.md + .opencode/), claude (CLAUDE.md), or all. Auto-detects if not specified.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Preview compilation without writing files (shows placement decisions)",
)
@click.option("--no-links", is_flag=True, help="Skip markdown link resolution")
@click.option("--chatmode", help="Chatmode to prepend to AGENTS.md files")
@click.option("--watch", is_flag=True, help="Auto-regenerate on changes")
@click.option("--validate", is_flag=True, help="Validate primitives without compiling")
@click.option(
    "--with-constitution/--no-constitution",
    default=True,
    show_default=True,
    help="Include Spec Kit constitution block at top if memory/constitution.md present",
)
# Distributed compilation options (Task 7)
@click.option(
    "--single-agents",
    is_flag=True,
    help="Force single-file compilation (legacy mode)",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Show detailed source attribution and optimizer analysis",
)
@click.option(
    "--local-only",
    is_flag=True,
    help="Ignore dependencies, compile only local primitives",
)
@click.option(
    "--clean",
    is_flag=True,
    help="Remove orphaned AGENTS.md files that are no longer generated",
)
@click.pass_context
def compile(
    ctx,
    output,
    target,
    dry_run,
    no_links,
    chatmode,
    watch,
    validate,
    with_constitution,
    single_agents,
    verbose,
    local_only,
    clean,
):
    """Compile APM context into distributed AGENTS.md files.

    By default, uses distributed compilation to generate multiple focused AGENTS.md
    files across your directory structure following the Minimal Context Principle.

    Use --single-agents for traditional single-file compilation when needed.

    Target platforms:
    * vscode/agents: Generates AGENTS.md + .github/ structure (VSCode/GitHub Copilot)
    * opencode: Generates AGENTS.md + .opencode/ structure (OpenCode)
    * claude: Generates CLAUDE.md + .claude/ structure (Claude Code)
    * all: Generates both targets (default)

    Advanced options:
    * --dry-run: Preview compilation without writing files (shows placement decisions)
    * --verbose: Show detailed source attribution and optimizer analysis
    * --local-only: Ignore dependencies, compile only local .apm/ primitives
    * --clean: Remove orphaned AGENTS.md files that are no longer generated
    """
    try:
        # Check if this is an APM project first
        from pathlib import Path

        if not Path("apm.yml").exists():
            _rich_error("[x] Not an APM project - no apm.yml found")
            _rich_info(" To initialize an APM project, run:")
            _rich_info("   apm init")
            sys.exit(1)

        # Check if there are any instruction files to compile
        from ..compilation.constitution import find_constitution

        apm_modules_exists = Path("apm_modules").exists()
        constitution_exists = find_constitution(Path(".")).exists()

        # Check if .apm directory has actual content
        apm_dir = Path(".apm")
        local_apm_has_content = apm_dir.exists() and (
            any(apm_dir.rglob("*.instructions.md"))
            or any(apm_dir.rglob("*.chatmode.md"))
        )

        # If no primitive sources exist, check deeper to provide better feedback
        if (
            not apm_modules_exists
            and not local_apm_has_content
            and not constitution_exists
        ):
            # Check if .apm directories exist but are empty
            has_empty_apm = (
                apm_dir.exists()
                and not any(apm_dir.rglob("*.instructions.md"))
                and not any(apm_dir.rglob("*.chatmode.md"))
            )

            if has_empty_apm:
                _rich_error("[x] No instruction files found in .apm/ directory")
                _rich_info(" To add instructions, create files like:")
                _rich_info("   .apm/instructions/coding-standards.instructions.md")
                _rich_info("   .apm/chatmodes/backend-engineer.chatmode.md")
            else:
                _rich_error("[x] No APM content found to compile")
                _rich_info(" To get started:")
                _rich_info("   1. Install APM dependencies: apm install <owner>/<repo>")
                _rich_info(
                    "   2. Or create local instructions: mkdir -p .apm/instructions"
                )
                _rich_info("   3. Then create .instructions.md or .chatmode.md files")

            if not dry_run:  # Don't exit on dry-run to allow testing
                sys.exit(1)

        # Validation-only mode
        if validate:
            _rich_info("Validating APM context...", symbol="gear")
            compiler = AgentsCompiler(".")
            try:
                primitives = discover_primitives(".")
            except Exception as e:
                _rich_error(f"Failed to discover primitives: {e}")
                _rich_info(f" Error details: {type(e).__name__}")
                sys.exit(1)
            validation_errors = compiler.validate_primitives(primitives)
            if validation_errors:
                _display_validation_errors(validation_errors)
                _rich_error(f"Validation failed with {len(validation_errors)} errors")
                sys.exit(1)
            _rich_success("All primitives validated successfully!", symbol="sparkles")
            _rich_info(f"Validated {primitives.count()} primitives:")
            _rich_info(f"  * {len(primitives.chatmodes)} chatmodes")
            _rich_info(f"  * {len(primitives.instructions)} instructions")
            _rich_info(f"  * {len(primitives.contexts)} contexts")
            # Show MCP dependency validation count
            try:
                from ..models.apm_package import APMPackage
                apm_pkg = APMPackage.from_apm_yml(Path("apm.yml"))
                mcp_count = len(apm_pkg.get_mcp_dependencies())
                if mcp_count > 0:
                    _rich_info(f"  * {mcp_count} MCP dependencies")
            except Exception:
                pass
            return

        # Watch mode
        if watch:
            _watch_mode(output, chatmode, no_links, dry_run)
            return

        _rich_info("Starting context compilation...", symbol="cogs")

        # Auto-detect target if not explicitly provided
        from ..core.target_detection import detect_target, get_target_description

        # Get config target from apm.yml if available
        config_target = None
        try:
            from ..models.apm_package import APMPackage

            apm_pkg = APMPackage.from_apm_yml(Path("apm.yml"))
            config_target = apm_pkg.target
        except Exception:
            # No apm.yml or parsing error - proceed with auto-detection
            pass

        detected_target, detection_reason = detect_target(
            project_root=Path("."),
            explicit_target=target,
            config_target=config_target,
        )

        # Map 'minimal' to 'vscode' for the compiler (AGENTS.md only, no folder integration)
        effective_target = detected_target if detected_target != "minimal" else "vscode"

        # Build config with distributed compilation flags (Task 7)
        config = CompilationConfig.from_apm_yml(
            output_path=output if output != "AGENTS.md" else None,
            chatmode=chatmode,
            resolve_links=not no_links if no_links else None,
            dry_run=dry_run,
            single_agents=single_agents,
            trace=verbose,
            local_only=local_only,
            debug=verbose,
            clean_orphaned=clean,
            target=effective_target,
        )
        config.with_constitution = with_constitution

        # Handle distributed vs single-file compilation
        if config.strategy == "distributed" and not single_agents:
            # Show target-aware message with detection reason
            if detected_target == "minimal":
                _rich_info(f"Compiling for AGENTS.md only ({detection_reason})")
                _rich_info(
                    " Create .github/ or .claude/ folder for full integration",
                    symbol="light_bulb",
                )
            elif detected_target == "vscode" or detected_target == "agents":
                _rich_info(
                    f"Compiling for AGENTS.md (VSCode/Copilot) - {detection_reason}"
                )
            elif detected_target == "opencode":
                _rich_info(f"Compiling for AGENTS.md (OpenCode) - {detection_reason}")
            elif detected_target == "claude":
                _rich_info(
                    f"Compiling for CLAUDE.md (Claude Code) - {detection_reason}"
                )
            else:  # "all"
                _rich_info(f"Compiling for AGENTS.md + CLAUDE.md - {detection_reason}")

            if dry_run:
                _rich_info(
                    "Dry run mode: showing placement without writing files",
                    symbol="eye",
                )
            if verbose:
                _rich_info(
                    "Verbose mode: showing source attribution and optimizer analysis",
                    symbol="magnifying_glass",
                )
        else:
            _rich_info("Using single-file compilation (legacy mode)", symbol="page")

        # Perform compilation
        compiler = AgentsCompiler(".")
        result = compiler.compile(config)

        if result.success:
            # Handle different compilation modes
            if config.strategy == "distributed" and not single_agents:
                # Distributed compilation results - output already shown by professional formatter
                # Just show final success message
                if dry_run:
                    # Success message for dry run already included in formatter output
                    pass
                else:
                    # Success message for actual compilation
                    _rich_success("Compilation completed successfully!", symbol="check")

            else:
                # Traditional single-file compilation - keep existing logic
                # Perform initial compilation in dry-run to get generated body (without constitution)
                intermediate_config = CompilationConfig(
                    output_path=config.output_path,
                    chatmode=config.chatmode,
                    resolve_links=config.resolve_links,
                    dry_run=True,  # force
                    with_constitution=config.with_constitution,
                    strategy="single-file",
                )
                intermediate_result = compiler.compile(intermediate_config)

                if intermediate_result.success:
                    # Perform constitution injection / preservation
                    from ..compilation.injector import ConstitutionInjector

                    injector = ConstitutionInjector(base_dir=".")
                    output_path = Path(config.output_path)
                    final_content, c_status, c_hash = injector.inject(
                        intermediate_result.content,
                        with_constitution=config.with_constitution,
                        output_path=output_path,
                    )

                    # Compute deterministic Build ID (12-char SHA256) over content with placeholder removed
                    import hashlib

                    from ..compilation.constants import BUILD_ID_PLACEHOLDER

                    lines = final_content.splitlines()
                    # Identify placeholder line index
                    try:
                        idx = lines.index(BUILD_ID_PLACEHOLDER)
                    except ValueError:
                        idx = None
                    hash_input_lines = [l for i, l in enumerate(lines) if i != idx]
                    hash_bytes = "\n".join(hash_input_lines).encode("utf-8")
                    build_id = hashlib.sha256(hash_bytes).hexdigest()[:12]
                    if idx is not None:
                        lines[idx] = f"<!-- Build ID: {build_id} -->"
                        final_content = "\n".join(lines) + (
                            "\n" if final_content.endswith("\n") else ""
                        )

                    if not dry_run:
                        # Only rewrite when content materially changes (creation, update, missing constitution case)
                        if c_status in ("CREATED", "UPDATED", "MISSING"):
                            try:
                                _atomic_write(output_path, final_content)
                            except OSError as e:
                                _rich_error(f"Failed to write final AGENTS.md: {e}")
                                sys.exit(1)
                        else:
                            _rich_info(
                                "No changes detected; preserving existing AGENTS.md for idempotency"
                            )

                    # Report success at the top
                    if dry_run:
                        _rich_success(
                            "Context compilation completed successfully (dry run)",
                            symbol="check",
                        )
                    else:
                        _rich_success(
                            f"Context compiled successfully to {output_path}",
                            symbol="sparkles",
                        )

                    stats = (
                        intermediate_result.stats
                    )  # timestamp removed; stats remain version + counts

                    # Add spacing before summary table
                    _rich_blank_line()

                    # Single comprehensive compilation summary table
                    try:
                        console = _get_console()
                        if console:
                            import os

                            from rich.table import Table

                            table = Table(
                                title="Compilation Summary",
                                show_header=True,
                                header_style="bold cyan",
                            )
                            table.add_column(
                                "Component", style="bold white", min_width=15
                            )
                            table.add_column("Count", style="cyan", min_width=8)
                            table.add_column("Details", style="white", min_width=20)

                            # Constitution row
                            constitution_details = f"Hash: {c_hash or '-'}"
                            table.add_row(
                                "Spec-kit Constitution", c_status, constitution_details
                            )

                            # Primitives rows
                            table.add_row(
                                "Instructions",
                                str(stats.get("instructions", 0)),
                                "[+] All validated",
                            )
                            table.add_row(
                                "Contexts",
                                str(stats.get("contexts", 0)),
                                "[+] All validated",
                            )
                            table.add_row(
                                "Chatmodes",
                                str(stats.get("chatmodes", 0)),
                                "[+] All validated",
                            )

                            # Output row with file size
                            try:
                                file_size = (
                                    os.path.getsize(output_path) if not dry_run else 0
                                )
                                size_str = (
                                    f"{file_size/1024:.1f}KB"
                                    if file_size > 0
                                    else "Preview"
                                )
                                output_details = f"{output_path.name} ({size_str})"
                            except:
                                output_details = f"{output_path.name}"

                            table.add_row("Output", "* SUCCESS", output_details)

                            console.print(table)
                        else:
                            # Fallback for no Rich console
                            _rich_info(
                                f"Processed {stats.get('primitives_found', 0)} primitives:"
                            )
                            _rich_info(
                                f"  * {stats.get('instructions', 0)} instructions"
                            )
                            _rich_info(f"  * {stats.get('contexts', 0)} contexts")
                            _rich_info(
                                f"Constitution status: {c_status} hash={c_hash or '-'}"
                            )
                    except Exception:
                        # Fallback for any errors
                        _rich_info(
                            f"Processed {stats.get('primitives_found', 0)} primitives:"
                        )
                        _rich_info(f"  * {stats.get('instructions', 0)} instructions")
                        _rich_info(f"  * {stats.get('contexts', 0)} contexts")
                        _rich_info(
                            f"Constitution status: {c_status} hash={c_hash or '-'}"
                        )

                    if dry_run:
                        preview = final_content[:500] + (
                            "..." if len(final_content) > 500 else ""
                        )
                        _rich_panel(
                            preview, title=" Generated Content Preview", style="cyan"
                        )
                    else:
                        next_steps = [
                            f"Review the generated {output} file",
                            "Install MCP dependencies: apm install",
                            "Execute agentic workflows: apm run <script> --param key=value",
                        ]
                        try:
                            console = _get_console()
                            if console:
                                from rich.panel import Panel

                                steps_content = "\n".join(
                                    f"* {step}" for step in next_steps
                                )
                                console.print(
                                    Panel(
                                        steps_content,
                                        title=" Next Steps",
                                        border_style="blue",
                                    )
                                )
                            else:
                                _rich_info("Next steps:")
                                for step in next_steps:
                                    click.echo(f"  * {step}")
                        except (ImportError, NameError):
                            _rich_info("Next steps:")
                            for step in next_steps:
                                click.echo(f"  * {step}")

        # Common error handling for both compilation modes
        # Note: Warnings are handled by professional formatters for distributed mode
        if config.strategy != "distributed" or single_agents:
            # Only show warnings for single-file mode (backward compatibility)
            if result.warnings:
                _rich_warning(
                    f"Compilation completed with {len(result.warnings)} warnings:"
                )
                for warning in result.warnings:
                    click.echo(f"  [!]  {warning}")

        if result.errors:
            _rich_error(f"Compilation failed with {len(result.errors)} errors:")
            for error in result.errors:
                click.echo(f"  [x] {error}")
            sys.exit(1)

        # Check for orphaned packages after successful compilation
        try:
            orphaned_packages = _check_orphaned_packages()
            if orphaned_packages:
                _rich_blank_line()
                _rich_warning(
                    f"[!] Found {len(orphaned_packages)} orphaned package(s) that were included in compilation:"
                )
                for pkg in orphaned_packages:
                    _rich_info(f"  * {pkg}")
                _rich_info(" Run 'apm prune' to remove orphaned packages")
        except Exception:
            pass  # Continue if orphan check fails

    except ImportError as e:
        _rich_error(f"Compilation module not available: {e}")
        _rich_info("This might be a development environment issue.")
        sys.exit(1)
    except Exception as e:
        _rich_error(f"Error during compilation: {e}")
        sys.exit(1)
