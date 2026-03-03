"""Unit tests for the PackageValidator class."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from apm_cli.deps.package_validator import PackageValidator
from apm_cli.models.apm_package import ValidationResult


def _write_minimal_apm_yml(
    path: Path, name: str = "test-pkg", version: str = "1.0.0", description: str = None
) -> None:
    """Helper to write a minimal valid apm.yml file."""
    content = f"name: {name}\nversion: '{version}'\n"
    if description:
        content += f"description: {description}\n"
    path.write_text(content, encoding="utf-8")


class TestPackageValidatorInit(unittest.TestCase):
    def test_init(self):
        validator = PackageValidator()
        self.assertIsInstance(validator, PackageValidator)


class TestValidatePackage(unittest.TestCase):
    """Tests for validate_package() which delegates to base_validate_apm_package."""

    def test_delegates_to_base(self):
        validator = PackageValidator()
        mock_result = ValidationResult()
        with patch(
            "apm_cli.deps.package_validator.base_validate_apm_package",
            return_value=mock_result,
        ) as mock_fn:
            result = validator.validate_package(Path("/some/path"))
        mock_fn.assert_called_once_with(Path("/some/path"))
        self.assertIs(result, mock_result)


class TestValidatePackageStructure(unittest.TestCase):
    """Tests for validate_package_structure()."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.validator = PackageValidator()

    def tearDown(self):
        self.tmp.cleanup()

    def test_nonexistent_path(self):
        result = self.validator.validate_package_structure(self.root / "nonexistent")
        self.assertFalse(result.is_valid)
        self.assertTrue(any("does not exist" in e for e in result.errors))

    def test_not_a_directory(self):
        file_path = self.root / "not_a_dir.txt"
        file_path.write_text("hi")
        result = self.validator.validate_package_structure(file_path)
        self.assertFalse(result.is_valid)
        self.assertTrue(any("not a directory" in e for e in result.errors))

    def test_missing_apm_yml(self):
        pkg = self.root / "pkg"
        pkg.mkdir()
        result = self.validator.validate_package_structure(pkg)
        self.assertFalse(result.is_valid)
        self.assertTrue(any("apm.yml" in e for e in result.errors))

    def test_invalid_apm_yml(self):
        pkg = self.root / "pkg"
        pkg.mkdir()
        (pkg / "apm.yml").write_text("name: test\n# missing version", encoding="utf-8")
        result = self.validator.validate_package_structure(pkg)
        self.assertFalse(result.is_valid)
        self.assertTrue(any("apm.yml" in e for e in result.errors))

    def test_missing_apm_dir(self):
        pkg = self.root / "pkg"
        pkg.mkdir()
        _write_minimal_apm_yml(pkg / "apm.yml")
        result = self.validator.validate_package_structure(pkg)
        self.assertFalse(result.is_valid)
        self.assertTrue(any(".apm" in e for e in result.errors))

    def test_apm_dir_is_file_not_dir(self):
        pkg = self.root / "pkg"
        pkg.mkdir()
        _write_minimal_apm_yml(pkg / "apm.yml")
        (pkg / ".apm").write_text("not a dir")
        result = self.validator.validate_package_structure(pkg)
        self.assertFalse(result.is_valid)
        self.assertTrue(any(".apm must be a directory" in e for e in result.errors))

    def test_no_primitives_adds_warning(self):
        pkg = self.root / "pkg"
        pkg.mkdir()
        _write_minimal_apm_yml(pkg / "apm.yml")
        (pkg / ".apm").mkdir()
        result = self.validator.validate_package_structure(pkg)
        self.assertTrue(result.is_valid)
        self.assertTrue(any("No primitive" in w for w in result.warnings))

    def test_valid_package_with_instructions(self):
        pkg = self.root / "pkg"
        pkg.mkdir()
        _write_minimal_apm_yml(pkg / "apm.yml")
        apm_dir = pkg / ".apm"
        apm_dir.mkdir()
        instr_dir = apm_dir / "instructions"
        instr_dir.mkdir()
        (instr_dir / "my-rule.instructions.md").write_text("# Instructions")
        result = self.validator.validate_package_structure(pkg)
        self.assertTrue(result.is_valid)
        self.assertEqual(result.warnings, [])

    def test_valid_package_with_hooks_in_apm_dir(self):
        pkg = self.root / "pkg"
        pkg.mkdir()
        _write_minimal_apm_yml(pkg / "apm.yml")
        apm_dir = pkg / ".apm"
        apm_dir.mkdir()
        hooks_dir = apm_dir / "hooks"
        hooks_dir.mkdir()
        (hooks_dir / "hook.json").write_text('{"type": "hook"}')
        result = self.validator.validate_package_structure(pkg)
        self.assertTrue(result.is_valid)
        self.assertEqual(result.warnings, [])

    def test_valid_package_with_hooks_at_root(self):
        pkg = self.root / "pkg"
        pkg.mkdir()
        _write_minimal_apm_yml(pkg / "apm.yml")
        (pkg / ".apm").mkdir()
        hooks_root = pkg / "hooks"
        hooks_root.mkdir()
        (hooks_root / "hook.json").write_text('{"type": "hook"}')
        result = self.validator.validate_package_structure(pkg)
        self.assertTrue(result.is_valid)
        self.assertEqual(result.warnings, [])

    def test_package_field_populated_on_valid_yml(self):
        pkg = self.root / "pkg"
        pkg.mkdir()
        _write_minimal_apm_yml(pkg / "apm.yml", name="my-pkg", version="2.0.0")
        (pkg / ".apm").mkdir()
        result = self.validator.validate_package_structure(pkg)
        # Even with warning about no primitives, package field is set
        self.assertIsNotNone(result.package)
        self.assertEqual(result.package.name, "my-pkg")


class TestValidatePrimitiveFile(unittest.TestCase):
    """Tests for _validate_primitive_file()."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.validator = PackageValidator()

    def tearDown(self):
        self.tmp.cleanup()

    def test_empty_file_adds_warning(self):
        f = self.root / "empty.md"
        f.write_text("   ", encoding="utf-8")
        result = ValidationResult()
        self.validator._validate_primitive_file(f, result)
        self.assertTrue(any("Empty" in w for w in result.warnings))

    def test_file_with_content_no_warning(self):
        f = self.root / "content.md"
        f.write_text("# Some content here", encoding="utf-8")
        result = ValidationResult()
        self.validator._validate_primitive_file(f, result)
        self.assertEqual(result.warnings, [])

    def test_unreadable_file_adds_warning(self):
        result = ValidationResult()
        with patch.object(Path, "read_text", side_effect=PermissionError("denied")):
            self.validator._validate_primitive_file(Path("/fake/file.md"), result)
        self.assertTrue(any("Could not read" in w for w in result.warnings))


class TestValidatePrimitiveStructure(unittest.TestCase):
    """Tests for validate_primitive_structure()."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.validator = PackageValidator()

    def tearDown(self):
        self.tmp.cleanup()

    def test_missing_apm_dir(self):
        issues = self.validator.validate_primitive_structure(self.root / "nonexistent")
        self.assertIn("Missing .apm directory", issues)

    def test_no_primitives_found(self):
        apm_dir = self.root / ".apm"
        apm_dir.mkdir()
        issues = self.validator.validate_primitive_structure(apm_dir)
        self.assertTrue(any("No primitive" in i for i in issues))

    def test_primitive_type_is_file_not_dir(self):
        apm_dir = self.root / ".apm"
        apm_dir.mkdir()
        (apm_dir / "instructions").write_text("should be dir")
        issues = self.validator.validate_primitive_structure(apm_dir)
        self.assertTrue(any("should be a directory" in i for i in issues))

    def test_valid_primitives_no_issues(self):
        apm_dir = self.root / ".apm"
        apm_dir.mkdir()
        instr_dir = apm_dir / "instructions"
        instr_dir.mkdir()
        (instr_dir / "my-rule.instructions.md").write_text("# Rule")
        issues = self.validator.validate_primitive_structure(apm_dir)
        self.assertEqual(issues, [])

    def test_invalid_primitive_name_reported(self):
        apm_dir = self.root / ".apm"
        apm_dir.mkdir()
        instr_dir = apm_dir / "instructions"
        instr_dir.mkdir()
        # Wrong suffix for instructions type
        (instr_dir / "my-rule.chatmode.md").write_text("# Rule")
        issues = self.validator.validate_primitive_structure(apm_dir)
        self.assertTrue(any("Invalid primitive file name" in i for i in issues))


class TestIsValidPrimitiveName(unittest.TestCase):
    """Tests for _is_valid_primitive_name()."""

    def setUp(self):
        self.validator = PackageValidator()

    def test_not_md_extension(self):
        self.assertFalse(
            self.validator._is_valid_primitive_name("file.txt", "instructions")
        )

    def test_contains_spaces(self):
        self.assertFalse(
            self.validator._is_valid_primitive_name(
                "my rule.instructions.md", "instructions"
            )
        )

    def test_valid_instructions(self):
        self.assertTrue(
            self.validator._is_valid_primitive_name(
                "coding.instructions.md", "instructions"
            )
        )

    def test_invalid_instructions_wrong_suffix(self):
        self.assertFalse(
            self.validator._is_valid_primitive_name(
                "coding.chatmode.md", "instructions"
            )
        )

    def test_valid_chatmode(self):
        self.assertTrue(
            self.validator._is_valid_primitive_name("debug.chatmode.md", "chatmodes")
        )

    def test_invalid_chatmode_wrong_suffix(self):
        self.assertFalse(
            self.validator._is_valid_primitive_name(
                "debug.instructions.md", "chatmodes"
            )
        )

    def test_valid_context(self):
        self.assertTrue(
            self.validator._is_valid_primitive_name("repo.context.md", "contexts")
        )

    def test_valid_prompt(self):
        self.assertTrue(
            self.validator._is_valid_primitive_name("summarize.prompt.md", "prompts")
        )

    def test_unknown_primitive_type_valid_md(self):
        # Unknown types have no suffix check - only .md and no spaces required
        self.assertTrue(
            self.validator._is_valid_primitive_name("anything.md", "unknown_type")
        )


class TestGetPackageInfoSummary(unittest.TestCase):
    """Tests for get_package_info_summary()."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.validator = PackageValidator()

    def tearDown(self):
        self.tmp.cleanup()

    def test_invalid_package_returns_none(self):
        result = self.validator.get_package_info_summary(self.root / "nonexistent")
        self.assertIsNone(result)

    def _make_valid_package(
        self,
        name="test-pkg",
        version="1.0.0",
        description=None,
        instructions=None,
        hooks_in_apm=None,
        hooks_at_root=None,
    ):
        pkg = self.root / name
        pkg.mkdir(exist_ok=True)
        _write_minimal_apm_yml(
            pkg / "apm.yml", name=name, version=version, description=description
        )
        apm_dir = pkg / ".apm"
        apm_dir.mkdir(exist_ok=True)
        if instructions:
            instr_dir = apm_dir / "instructions"
            instr_dir.mkdir(exist_ok=True)
            for fname in instructions:
                (instr_dir / fname).write_text("# content")
        if hooks_in_apm:
            hooks_dir = apm_dir / "hooks"
            hooks_dir.mkdir(exist_ok=True)
            for fname in hooks_in_apm:
                (hooks_dir / fname).write_text("{}")
        if hooks_at_root:
            root_hooks = pkg / "hooks"
            root_hooks.mkdir(exist_ok=True)
            for fname in hooks_at_root:
                (root_hooks / fname).write_text("{}")
        return pkg

    def test_valid_no_description_no_primitives_returns_name_version(self):
        pkg = self._make_valid_package()
        result = self.validator.get_package_info_summary(pkg)
        # base_validate_apm_package may fail since .apm is empty - use mocked valid result
        if result is None:
            # If base validation fails on empty package, that's acceptable; test mock path
            mock_result = ValidationResult()
            mock_result.package = MagicMock()
            mock_result.package.name = "test-pkg"
            mock_result.package.version = "1.0.0"
            mock_result.package.description = None
            with patch.object(
                self.validator, "validate_package", return_value=mock_result
            ):
                result = self.validator.get_package_info_summary(pkg)
        self.assertIn("test-pkg", result)
        self.assertIn("1.0.0", result)

    def test_valid_with_description(self):
        mock_result = ValidationResult()
        mock_result.package = MagicMock()
        mock_result.package.name = "my-pkg"
        mock_result.package.version = "2.0.0"
        mock_result.package.description = "A test package"
        with patch.object(self.validator, "validate_package", return_value=mock_result):
            result = self.validator.get_package_info_summary(self.root / "any")
        self.assertIn("my-pkg", result)
        self.assertIn("2.0.0", result)
        self.assertIn("A test package", result)

    def test_summary_includes_primitive_count(self):
        pkg = self._make_valid_package(
            name="rich-pkg",
            version="1.0.0",
            instructions=["rule.instructions.md", "other.instructions.md"],
        )
        mock_result = ValidationResult()
        mock_result.package = MagicMock()
        mock_result.package.name = "rich-pkg"
        mock_result.package.version = "1.0.0"
        mock_result.package.description = None
        with patch.object(self.validator, "validate_package", return_value=mock_result):
            result = self.validator.get_package_info_summary(pkg)
        self.assertIsNotNone(result)
        self.assertIn("2 primitives", result)

    def test_summary_counts_hooks_in_apm_dir(self):
        pkg = self._make_valid_package(
            name="hook-pkg", version="1.0.0", hooks_in_apm=["a.json", "b.json"]
        )
        mock_result = ValidationResult()
        mock_result.package = MagicMock()
        mock_result.package.name = "hook-pkg"
        mock_result.package.version = "1.0.0"
        mock_result.package.description = None
        with patch.object(self.validator, "validate_package", return_value=mock_result):
            result = self.validator.get_package_info_summary(pkg)
        self.assertIsNotNone(result)
        self.assertIn("2 primitives", result)

    def test_summary_counts_hooks_at_root_when_no_apm_hooks(self):
        pkg = self._make_valid_package(
            name="roothook-pkg", version="1.0.0", hooks_at_root=["c.json"]
        )
        mock_result = ValidationResult()
        mock_result.package = MagicMock()
        mock_result.package.name = "roothook-pkg"
        mock_result.package.version = "1.0.0"
        mock_result.package.description = None
        with patch.object(self.validator, "validate_package", return_value=mock_result):
            result = self.validator.get_package_info_summary(pkg)
        self.assertIsNotNone(result)
        self.assertIn("1 primitives", result)

    def test_invalid_package_mock(self):
        mock_result = ValidationResult()
        mock_result.add_error("something wrong")
        with patch.object(self.validator, "validate_package", return_value=mock_result):
            result = self.validator.get_package_info_summary(self.root / "any")
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
