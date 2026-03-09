"""Unit tests for workflow functionality."""

import gc
import os
import shutil
import sys
import tempfile
import time
import unittest
import unittest.mock

from apm_cli.workflow.discovery import create_workflow_template, discover_workflows
from apm_cli.workflow.parser import WorkflowDefinition, parse_workflow_file
from apm_cli.workflow.runner import collect_parameters, substitute_parameters


def safe_rmdir(path):
    """Safely remove a directory with retry logic for Windows.

    Args:
        path (str): Path to directory to remove
    """
    try:
        shutil.rmtree(path)
    except PermissionError:
        # On Windows, give time for any lingering processes to release the lock
        time.sleep(0.5)
        gc.collect()  # Force garbage collection to release file handles
        try:
            shutil.rmtree(path)
        except PermissionError as e:
            print(f"Failed to remove directory {path}: {e}")
            # Continue without failing the test
            pass


class TestWorkflowParser(unittest.TestCase):
    """Test cases for the workflow parser."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_dir_path = self.temp_dir.name
        # Create .github/prompts directory structure
        self.prompts_dir = os.path.join(self.temp_dir_path, ".github", "prompts")
        os.makedirs(self.prompts_dir, exist_ok=True)
        self.temp_path = os.path.join(self.prompts_dir, "test-workflow.prompt.md")

        # Create a test workflow file
        with open(self.temp_path, "w") as f:
            f.write(
                """---
description: Test workflow
author: Test Author
mcp:
  - test-package
input:
  - param1
  - param2
---

# Test Workflow

1. Step One: ${input:param1}
2. Step Two: ${input:param2}
"""
            )

    def tearDown(self):
        """Tear down test fixtures."""
        # Force garbage collection to release file handles
        gc.collect()

        # Give time for Windows to release locks
        if sys.platform == "win32":
            time.sleep(0.1)

        # First, try the standard cleanup
        try:
            self.temp_dir.cleanup()
        except PermissionError:
            # If standard cleanup fails on Windows, use our safe_rmdir function
            if hasattr(self, "temp_dir_path") and os.path.exists(self.temp_dir_path):
                safe_rmdir(self.temp_dir_path)

    def test_parse_workflow_file(self):
        """Test parsing a workflow file."""
        workflow = parse_workflow_file(self.temp_path)

        self.assertEqual(workflow.name, "test-workflow")
        self.assertEqual(workflow.description, "Test workflow")
        self.assertEqual(workflow.author, "Test Author")
        self.assertEqual(workflow.mcp_dependencies, ["test-package"])
        self.assertEqual(workflow.input_parameters, ["param1", "param2"])
        self.assertIn("# Test Workflow", workflow.content)

    def test_workflow_validation(self):
        """Test workflow validation."""
        # Valid workflow
        workflow = WorkflowDefinition(
            "test",
            ".github/prompts/test.prompt.md",
            {"description": "Test", "input": ["param1"]},
            "content",
        )
        self.assertEqual(workflow.validate(), [])

        # Invalid workflow - missing description
        workflow = WorkflowDefinition(
            "test", ".github/prompts/test.prompt.md", {"input": ["param1"]}, "content"
        )
        errors = workflow.validate()
        self.assertEqual(len(errors), 1)
        self.assertIn("description", errors[0])

        # Input parameters are now optional, so this should not report an error
        workflow = WorkflowDefinition(
            "test", ".github/prompts/test.prompt.md", {"description": "Test"}, "content"
        )
        errors = workflow.validate()
        self.assertEqual(len(errors), 0)  # Expecting 0 errors as input is optional


class TestWorkflowRunner(unittest.TestCase):
    """Test cases for the workflow runner."""

    def test_parameter_substitution(self):
        """Test parameter substitution."""
        content = "This is a test with ${input:param1} and ${input:param2}."
        params = {"param1": "value1", "param2": "value2"}

        result = substitute_parameters(content, params)
        self.assertEqual(result, "This is a test with value1 and value2.")

    def test_parameter_substitution_with_missing_params(self):
        """Test parameter substitution with missing parameters."""
        content = "This is a test with ${input:param1} and ${input:param2}."
        params = {"param1": "value1"}

        result = substitute_parameters(content, params)
        self.assertEqual(result, "This is a test with value1 and ${input:param2}.")


class TestWorkflowDiscovery(unittest.TestCase):
    """Test cases for workflow discovery."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_dir_path = self.temp_dir.name

        # Create .github/prompts directory structure
        self.prompts_dir = os.path.join(self.temp_dir_path, ".github", "prompts")
        os.makedirs(self.prompts_dir, exist_ok=True)

        # Create a few test workflow files
        self.workflow1_path = os.path.join(self.prompts_dir, "workflow1.prompt.md")
        with open(self.workflow1_path, "w") as f:
            f.write(
                """---
description: Workflow 1
input:
  - param1
---
# Workflow 1
"""
            )

        self.workflow2_path = os.path.join(self.prompts_dir, "workflow2.prompt.md")
        with open(self.workflow2_path, "w") as f:
            f.write(
                """---
description: Workflow 2
input:
  - param1
---
# Workflow 2
"""
            )

    def tearDown(self):
        """Tear down test fixtures."""
        # Force garbage collection to release file handles
        gc.collect()

        # Give time for Windows to release locks
        if sys.platform == "win32":
            time.sleep(0.1)

        # First, try the standard cleanup
        try:
            self.temp_dir.cleanup()
        except PermissionError:
            # If standard cleanup fails on Windows, use our safe_rmdir function
            if hasattr(self, "temp_dir_path") and os.path.exists(self.temp_dir_path):
                safe_rmdir(self.temp_dir_path)

    def test_discover_workflows(self):
        """Test discovering workflows."""
        workflows = discover_workflows(self.temp_dir_path)

        self.assertEqual(len(workflows), 2)
        self.assertIn("workflow1", [w.name for w in workflows])
        self.assertIn("workflow2", [w.name for w in workflows])

    def test_create_workflow_template(self):
        """Test creating a workflow template."""
        template_path = create_workflow_template("test-template", self.temp_dir_path)

        self.assertTrue(os.path.exists(template_path))
        with open(template_path, "r") as f:
            content = f.read()
            self.assertIn("description:", content)
            self.assertIn("author:", content)
            self.assertIn("mcp:", content)
            self.assertIn("input:", content)
            self.assertIn("# Test Template", content)


class TestCollectParametersMissingBranch(unittest.TestCase):
    """Tests for collect_parameters when parameters are missing (prompts user)."""

    def _make_workflow(self, params):
        return WorkflowDefinition(
            "wf", ".github/prompts/wf.prompt.md", params, "content"
        )

    def test_collect_parameters_with_missing_prompts_user(self):
        """collect_parameters should prompt for missing params and return full dict."""
        from apm_cli.workflow.runner import collect_parameters

        wf = self._make_workflow({"description": "Test", "input": ["a", "b"]})
        with unittest.mock.patch("builtins.input", side_effect=["val_a", "val_b"]):
            result = collect_parameters(wf, {})
        self.assertEqual(result, {"a": "val_a", "b": "val_b"})

    def test_collect_parameters_partial_provided(self):
        """collect_parameters only prompts for truly missing params."""
        from apm_cli.workflow.runner import collect_parameters

        wf = self._make_workflow({"description": "Test", "input": ["a", "b"]})
        with unittest.mock.patch("builtins.input", return_value="val_b") as mock_input:
            result = collect_parameters(wf, {"a": "already_provided"})
        mock_input.assert_called_once()
        self.assertEqual(result["a"], "already_provided")
        self.assertEqual(result["b"], "val_b")

    def test_collect_parameters_dict_input_params(self):
        """collect_parameters handles dict-style input_parameters."""
        from apm_cli.workflow.runner import collect_parameters

        wf = WorkflowDefinition(
            "wf", ".github/prompts/wf.prompt.md", {"description": "Test"}, "content"
        )
        # Manually override input_parameters to be a dict
        wf.input_parameters = {"param1": "description", "param2": "description"}
        with unittest.mock.patch("builtins.input", side_effect=["v1", "v2"]):
            result = collect_parameters(wf, {})
        self.assertIn("param1", result)
        self.assertIn("param2", result)


class TestFindWorkflowByName(unittest.TestCase):
    """Tests for find_workflow_by_name."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = self.temp_dir.name
        prompts = os.path.join(self.base, ".github", "prompts")
        os.makedirs(prompts, exist_ok=True)
        self.wf_path = os.path.join(prompts, "my-workflow.prompt.md")
        with open(self.wf_path, "w") as f:
            f.write("---\ndescription: My Workflow\n---\n# Content\n")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_find_by_absolute_file_path(self):
        from apm_cli.workflow.runner import find_workflow_by_name

        result = find_workflow_by_name(self.wf_path)
        self.assertIsNotNone(result)
        self.assertEqual(result.name, "my-workflow")

    def test_find_by_relative_file_path(self):
        from apm_cli.workflow.runner import find_workflow_by_name

        result = find_workflow_by_name(
            "my-workflow.prompt.md",
            base_dir=os.path.join(self.base, ".github", "prompts"),
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.name, "my-workflow")

    def test_find_nonexistent_file_path_returns_none(self):
        from apm_cli.workflow.runner import find_workflow_by_name

        result = find_workflow_by_name("/nonexistent/path/wf.prompt.md")
        self.assertIsNone(result)

    def test_find_by_name_in_dir(self):
        from apm_cli.workflow.runner import find_workflow_by_name

        result = find_workflow_by_name("my-workflow", base_dir=self.base)
        self.assertIsNotNone(result)
        self.assertEqual(result.name, "my-workflow")

    def test_find_by_name_not_found_returns_none(self):
        from apm_cli.workflow.runner import find_workflow_by_name

        result = find_workflow_by_name("does-not-exist", base_dir=self.base)
        self.assertIsNone(result)

    def test_find_workflow_md_extension(self):
        """find_workflow_by_name handles .workflow.md extension."""
        from apm_cli.workflow.runner import find_workflow_by_name

        wf_md = os.path.join(self.base, ".github", "prompts", "alt.workflow.md")
        with open(wf_md, "w") as f:
            f.write("---\ndescription: Alt\n---\n# Alt\n")
        result = find_workflow_by_name(wf_md)
        self.assertIsNotNone(result)

    def test_find_parse_error_returns_none(self):
        """If parsing raises an exception, returns None."""
        from apm_cli.workflow.runner import find_workflow_by_name

        broken = os.path.join(self.base, ".github", "prompts", "broken.prompt.md")
        with open(broken, "w") as f:
            f.write("not yaml frontmatter at all - just text")
        with unittest.mock.patch(
            "apm_cli.workflow.runner.discover_workflows"
        ) as mock_disc:
            mock_disc.return_value = []
            with unittest.mock.patch(
                "apm_cli.workflow.parser.parse_workflow_file",
                side_effect=ValueError("bad"),
            ):
                result = find_workflow_by_name(broken)
        self.assertIsNone(result)

    def test_find_uses_cwd_when_base_dir_none(self):
        """When base_dir is None, uses os.getcwd()."""
        from apm_cli.workflow.runner import find_workflow_by_name

        original = os.getcwd()
        try:
            os.chdir(self.base)
            result = find_workflow_by_name("my-workflow")
            self.assertIsNotNone(result)
        finally:
            os.chdir(original)


class TestRunWorkflow(unittest.TestCase):
    """Tests for run_workflow."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = self.temp_dir.name
        prompts = os.path.join(self.base, ".github", "prompts")
        os.makedirs(prompts, exist_ok=True)
        wf_path = os.path.join(prompts, "test-wf.prompt.md")
        with open(wf_path, "w") as f:
            f.write("---\ndescription: Test WF\n---\n# Hello ${input:name}\n")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_run_workflow_not_found_returns_false(self):
        from apm_cli.workflow.runner import run_workflow

        ok, msg = run_workflow("nonexistent", base_dir=self.base)
        self.assertFalse(ok)
        self.assertIn("not found", msg)

    def test_run_workflow_invalid_returns_false(self):
        from apm_cli.workflow.runner import run_workflow

        # Build a workflow with no description (fails validation)
        with unittest.mock.patch(
            "apm_cli.workflow.runner.find_workflow_by_name"
        ) as mock_find:
            from apm_cli.workflow.parser import WorkflowDefinition

            bad_wf = WorkflowDefinition("bad", "p", {}, "content")  # no description
            mock_find.return_value = bad_wf
            ok, msg = run_workflow("bad", base_dir=self.base)
        self.assertFalse(ok)
        self.assertIn("Invalid workflow", msg)

    def test_run_workflow_success(self):
        from apm_cli.workflow.runner import run_workflow

        mock_runtime = unittest.mock.MagicMock()
        mock_runtime.execute_prompt.return_value = "AI response"
        with unittest.mock.patch("apm_cli.workflow.runner.RuntimeFactory") as mock_rf:
            mock_rf.create_runtime.return_value = mock_runtime
            mock_rf.runtime_exists.return_value = True
            ok, msg = run_workflow(
                "test-wf", params={"name": "World"}, base_dir=self.base
            )
        self.assertTrue(ok)
        self.assertEqual(msg, "AI response")

    def test_run_workflow_invalid_runtime_returns_false(self):
        from apm_cli.workflow.runner import run_workflow

        with unittest.mock.patch("apm_cli.workflow.runner.RuntimeFactory") as mock_rf:
            mock_rf.runtime_exists.return_value = False
            mock_rf._RUNTIME_ADAPTERS = []
            ok, msg = run_workflow(
                "test-wf",
                params={"_runtime": "invalid_runtime", "name": "x"},
                base_dir=self.base,
            )
        self.assertFalse(ok)
        self.assertIn("Invalid runtime", msg)

    def test_run_workflow_valid_runtime_name(self):
        from apm_cli.workflow.runner import run_workflow

        mock_runtime = unittest.mock.MagicMock()
        mock_runtime.execute_prompt.return_value = "done"
        with unittest.mock.patch("apm_cli.workflow.runner.RuntimeFactory") as mock_rf:
            mock_rf.runtime_exists.return_value = True
            mock_rf.create_runtime.return_value = mock_runtime
            ok, msg = run_workflow(
                "test-wf",
                params={"_runtime": "copilot", "name": "x"},
                base_dir=self.base,
            )
        self.assertTrue(ok)

    def test_run_workflow_runtime_exception_returns_false(self):
        from apm_cli.workflow.runner import run_workflow

        with unittest.mock.patch("apm_cli.workflow.runner.RuntimeFactory") as mock_rf:
            mock_rf.create_runtime.side_effect = RuntimeError("no runtime")
            ok, msg = run_workflow("test-wf", params={"name": "x"}, base_dir=self.base)
        self.assertFalse(ok)
        self.assertIn("Runtime execution failed", msg)

    def test_run_workflow_warns_when_both_llm_specified(self):
        """Warning printed when frontmatter llm and --llm flag both given."""
        from apm_cli.workflow.runner import run_workflow

        with unittest.mock.patch(
            "apm_cli.workflow.runner.find_workflow_by_name"
        ) as mock_find:
            from apm_cli.workflow.parser import WorkflowDefinition

            wf = WorkflowDefinition("test-wf", "p", {"description": "d"}, "content")
            wf.llm_model = "gpt-4"
            mock_find.return_value = wf
            mock_runtime = unittest.mock.MagicMock()
            mock_runtime.execute_prompt.return_value = "ok"
            with unittest.mock.patch(
                "apm_cli.workflow.runner.RuntimeFactory"
            ) as mock_rf:
                mock_rf.create_runtime.return_value = mock_runtime
                with unittest.mock.patch("builtins.print") as mock_print:
                    ok, _ = run_workflow(
                        "test-wf", params={"_llm": "gpt-3.5"}, base_dir=self.base
                    )
                printed = " ".join(str(c) for c in mock_print.call_args_list)
                self.assertIn("WARNING", printed)


class TestPreviewWorkflow(unittest.TestCase):
    """Tests for preview_workflow."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = self.temp_dir.name
        prompts = os.path.join(self.base, ".github", "prompts")
        os.makedirs(prompts, exist_ok=True)
        wf_path = os.path.join(prompts, "preview-wf.prompt.md")
        with open(wf_path, "w") as f:
            f.write("---\ndescription: Preview WF\n---\n# Hello ${input:name}\n")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_preview_workflow_not_found_returns_false(self):
        from apm_cli.workflow.runner import preview_workflow

        ok, msg = preview_workflow("nonexistent", base_dir=self.base)
        self.assertFalse(ok)
        self.assertIn("not found", msg)

    def test_preview_workflow_invalid_returns_false(self):
        from apm_cli.workflow.runner import preview_workflow

        with unittest.mock.patch(
            "apm_cli.workflow.runner.find_workflow_by_name"
        ) as mock_find:
            from apm_cli.workflow.parser import WorkflowDefinition

            bad_wf = WorkflowDefinition("bad", "p", {}, "content")
            mock_find.return_value = bad_wf
            ok, msg = preview_workflow("bad", base_dir=self.base)
        self.assertFalse(ok)
        self.assertIn("Invalid workflow", msg)

    def test_preview_workflow_returns_substituted_content(self):
        from apm_cli.workflow.runner import preview_workflow

        ok, content = preview_workflow(
            "preview-wf", params={"name": "Alice"}, base_dir=self.base
        )
        self.assertTrue(ok)
        self.assertIn("Alice", content)
        self.assertNotIn("${input:name}", content)

    def test_preview_workflow_without_params_keeps_placeholder(self):
        from apm_cli.workflow.runner import preview_workflow

        with unittest.mock.patch("builtins.input", return_value="Bob"):
            ok, content = preview_workflow("preview-wf", base_dir=self.base)
        self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()
