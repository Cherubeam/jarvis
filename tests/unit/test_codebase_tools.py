"""Tests for packages.core.tools.codebase_tools."""

import pytest
from pathlib import Path

from packages.core.tools.codebase_tools import make_codebase_tools


@pytest.fixture
def project_dir(tmp_path):
    """Create a minimal project structure for testing."""
    # Create some files
    (tmp_path / "README.md").write_text("# Test Project\n")
    (tmp_path / "packages").mkdir()
    (tmp_path / "packages" / "core").mkdir()
    (tmp_path / "packages" / "core" / "main.py").write_text('"""Main module."""\nprint("hello")\n')
    (tmp_path / "packages" / "core" / "__init__.py").write_text("")
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "codebase_map.md").write_text("# Map\nTest map content\n")
    return tmp_path


@pytest.fixture
def tools(project_dir):
    """Create codebase tools from the test project."""
    return {t.name: t for t in make_codebase_tools(project_dir)}


class TestReadSourceFile:
    def test_read_existing_file(self, tools, project_dir):
        result = tools["read_source_file"].execute(path="README.md")
        assert "# Test Project" in result

    def test_read_nested_file(self, tools, project_dir):
        result = tools["read_source_file"].execute(path="packages/core/main.py")
        assert 'print("hello")' in result

    def test_read_nonexistent_file(self, tools):
        result = tools["read_source_file"].execute(path="nonexistent.py")
        assert "Error" in result
        assert "not found" in result

    def test_path_traversal_blocked(self, tools):
        result = tools["read_source_file"].execute(path="../../../etc/passwd")
        assert "Error" in result
        assert "outside" in result

    def test_large_file_rejected(self, tools, project_dir):
        large_file = project_dir / "large.py"
        large_file.write_text("x" * 60_000)
        result = tools["read_source_file"].execute(path="large.py")
        assert "Error" in result
        assert "too large" in result.lower()


class TestSearchCode:
    def test_search_finds_match(self, tools, project_dir):
        result = tools["search_code"].execute(pattern="hello")
        assert "main.py" in result
        assert "hello" in result

    def test_search_no_matches(self, tools):
        result = tools["search_code"].execute(pattern="nonexistent_pattern_xyz")
        assert "No matches" in result

    def test_search_invalid_regex(self, tools):
        result = tools["search_code"].execute(pattern="[invalid")
        assert "Error" in result
        assert "regex" in result.lower()

    def test_search_with_glob_filter(self, tools, project_dir):
        result = tools["search_code"].execute(pattern="Test Project", glob="**/*.md")
        assert "README.md" in result

    def test_search_respects_max_results(self, tools, project_dir):
        # Create a file with many matching lines
        many_lines = "\n".join(f"match_line_{i}" for i in range(100))
        (project_dir / "many.py").write_text(many_lines)
        result = tools["search_code"].execute(pattern="match_line", max_results=5)
        assert "Truncated" in result


class TestListDirectory:
    def test_list_root(self, tools, project_dir):
        result = tools["list_directory"].execute()
        assert "packages/" in result
        assert "README.md" in result

    def test_list_subdirectory(self, tools, project_dir):
        result = tools["list_directory"].execute(path="packages/core")
        assert "main.py" in result

    def test_list_nonexistent_directory(self, tools):
        result = tools["list_directory"].execute(path="nonexistent")
        assert "Error" in result

    def test_path_traversal_blocked(self, tools):
        result = tools["list_directory"].execute(path="../../../")
        assert "Error" in result

    def test_filters_pycache(self, tools, project_dir):
        (project_dir / "__pycache__").mkdir()
        (project_dir / "__pycache__" / "test.pyc").write_bytes(b"")
        result = tools["list_directory"].execute()
        assert "__pycache__" not in result


class TestReadArchitectureMap:
    def test_reads_map(self, tools, project_dir):
        result = tools["read_architecture_map"].execute()
        assert "# Map" in result
        assert "Test map content" in result

    def test_missing_map(self, tools, project_dir):
        (project_dir / "data" / "codebase_map.md").unlink()
        result = tools["read_architecture_map"].execute()
        assert "Error" in result
        assert "not found" in result


class TestToolFormat:
    def test_all_tools_have_litellm_format(self, tools):
        for name, tool in tools.items():
            fmt = tool.to_litellm_format()
            assert fmt["type"] == "function"
            assert fmt["function"]["name"] == name
            assert "parameters" in fmt["function"]

    def test_factory_returns_four_tools(self, project_dir):
        tools = make_codebase_tools(project_dir)
        assert len(tools) == 4
        names = {t.name for t in tools}
        assert names == {"read_source_file", "search_code", "list_directory", "read_architecture_map"}
