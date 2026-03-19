"""APM compile watch mode."""

import time

import click

from ...constants import AGENTS_MD_FILENAME, APM_DIR, APM_YML_FILENAME
from ...compilation import AgentsCompiler, CompilationConfig
from ...utils.console import _rich_error, _rich_info, _rich_success, _rich_warning


def _watch_mode(output, chatmode, no_links, dry_run):
    """Watch for changes in .apm/ directories and auto-recompile."""
    try:
        # Try to import watchdog for file system monitoring
        from pathlib import Path

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
                # Only react to relevant files
                if not event.src_path.endswith(".md") and not event.src_path.endswith(APM_YML_FILENAME):
                    return
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
                        output_path=self.output if self.output != AGENTS_MD_FILENAME else None,
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
        if Path(APM_DIR).exists():
            observer.schedule(event_handler, APM_DIR, recursive=True)
            watch_paths.append(f"{APM_DIR}/")

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
        if Path(APM_YML_FILENAME).exists():
            observer.schedule(event_handler, ".", recursive=False)
            watch_paths.append(APM_YML_FILENAME)

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
            output_path=output if output != AGENTS_MD_FILENAME else None,
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
        import sys
        sys.exit(1)
    except Exception as e:
        _rich_error(f"Error in watch mode: {e}")
        import sys
        sys.exit(1)
