"""Tests for packages.core.tools.codebase_tools."""

import pytest

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
        assert result == "# Test Project\n"

    def test_read_nested_file(self, tools, project_dir):
        result = tools["read_source_file"].execute(path="packages/core/main.py")
        assert result == '"""Main module."""\nprint("hello")\n'

    def test_read_nonexistent_file(self, tools):
        result = tools["read_source_file"].execute(path="nonexistent.py")
        assert result == "Error: File not found: nonexistent.py"

    def test_path_traversal_blocked(self, tools):
        result = tools["read_source_file"].execute(path="../../../etc/passwd")
        assert result.startswith("Error: Path '")
        assert "outside the project directory" in result

    def test_large_file_rejected(self, tools, project_dir):
        large_file = project_dir / "large.py"
        large_file.write_text("x" * 60_000)
        result = tools["read_source_file"].execute(path="large.py")
        assert result.startswith("Error: File too large (")
        assert "60000 bytes" in result
        assert "max 50000" in result


class TestSearchCode:
    def test_search_finds_match(self, tools, project_dir):
        result = tools["search_code"].execute(pattern="hello")
        # Format: file:line: content
        assert 'packages/core/main.py:2: print("hello")' in result

    def test_search_result_format_colon_separated(self, tools, project_dir):
        result = tools["search_code"].execute(pattern="Main module")
        # Verify exact format: relative_path:line_number: line_content
        assert 'packages/core/main.py:1: """Main module."""' in result

    def test_search_no_matches(self, tools):
        result = tools["search_code"].execute(pattern="nonexistent_pattern_xyz")
        assert result == "No matches found for pattern 'nonexistent_pattern_xyz' in '**/*.py'."

    def test_search_invalid_regex(self, tools):
        result = tools["search_code"].execute(pattern="[invalid")
        assert result.startswith("Error: Invalid regex pattern:")

    def test_search_with_glob_filter(self, tools, project_dir):
        result = tools["search_code"].execute(pattern="Test Project", glob="**/*.md")
        assert "README.md:1: # Test Project" in result

    def test_search_respects_max_results(self, tools, project_dir):
        # Create a file with many matching lines
        many_lines = "\n".join(f"match_line_{i}" for i in range(100))
        (project_dir / "many.py").write_text(many_lines)
        result = tools["search_code"].execute(pattern="match_line", max_results=5)
        assert result.endswith("[Truncated at 5 results]")

    def test_search_skips_pycache(self, tools, project_dir):
        pycache = project_dir / "__pycache__"
        pycache.mkdir()
        (pycache / "cached.py").write_text("hello_from_cache")
        result = tools["search_code"].execute(pattern="hello_from_cache", glob="**/*.py")
        assert result == "No matches found for pattern 'hello_from_cache' in '**/*.py'."


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
        assert result == "Error: Not a directory: nonexistent"

    def test_path_traversal_blocked(self, tools):
        result = tools["list_directory"].execute(path="../../../")
        assert result.startswith("Error: Path '")
        assert "outside the project directory" in result

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
        assert result == "Error: Codebase map not found. Run scripts/generate_codebase_map.py to generate it."


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
        assert names == {
            "read_source_file",
            "search_code",
            "list_directory",
            "read_architecture_map",
        }


class TestSchemaValidation:
    """Verify parameter schemas to kill dict key/value mutations."""

    def test_read_source_file_schema(self, tools):
        params = tools["read_source_file"].parameters
        assert params["type"] == "object"
        assert set(params["properties"].keys()) == {"path"}
        assert params["properties"]["path"]["type"] == "string"
        assert params["required"] == ["path"]

    def test_search_code_schema(self, tools):
        params = tools["search_code"].parameters
        assert params["type"] == "object"
        assert set(params["properties"].keys()) == {"pattern", "glob", "max_results"}
        assert params["properties"]["pattern"]["type"] == "string"
        assert params["properties"]["glob"]["type"] == "string"
        assert params["properties"]["glob"]["default"] == "**/*.py"
        assert params["properties"]["max_results"]["type"] == "integer"
        assert params["properties"]["max_results"]["default"] == 50
        assert params["required"] == ["pattern"]

    def test_list_directory_schema(self, tools):
        params = tools["list_directory"].parameters
        assert params["type"] == "object"
        assert set(params["properties"].keys()) == {"path", "pattern"}
        assert params["properties"]["path"]["type"] == "string"
        assert params["properties"]["path"]["default"] == ""
        assert params["properties"]["pattern"]["type"] == "string"
        assert params["properties"]["pattern"]["default"] == "*"
        assert params["required"] == []

    def test_read_architecture_map_schema(self, tools):
        params = tools["read_architecture_map"].parameters
        assert params["type"] == "object"
        assert params["properties"] == {}
        assert params["required"] == []


class TestAdditionalEdgeCases:
    """Tests targeting specific surviving mutation patterns."""

    def test_path_traversal_exact_error(self, tools):
        result = tools["read_source_file"].execute(path="../../../etc/passwd")
        assert result == "Error: Path '../../../etc/passwd' is outside the project directory."

    def test_list_dir_path_traversal_exact_error(self, tools):
        result = tools["list_directory"].execute(path="../../../")
        assert result == "Error: Path '../../../' is outside the project directory."

    def test_large_file_exact_error_format(self, tools, project_dir):
        large_file = project_dir / "big.py"
        large_file.write_text("x" * 60_000)
        result = tools["read_source_file"].execute(path="big.py")
        assert result == "Error: File too large (60000 bytes, max 50000)."

    def test_binary_file_error(self, tools, project_dir):
        binary_file = project_dir / "data.bin"
        binary_file.write_bytes(b"\x00\x01\x80\xff" * 100)
        result = tools["read_source_file"].execute(path="data.bin")
        assert result == "Error: Cannot read binary file: data.bin"

    def test_list_directory_dir_suffix(self, tools, project_dir):
        """Directories get a / suffix in output."""
        result = tools["list_directory"].execute()
        # packages/ is a directory, should have trailing /
        for line in result.split("\n"):
            if "packages" in line:
                assert line.endswith("/")
                break

    def test_list_directory_empty(self, tools, project_dir):
        empty_dir = project_dir / "empty"
        empty_dir.mkdir()
        result = tools["list_directory"].execute(path="empty")
        assert result == "Empty directory: empty"

    def test_list_directory_pattern_filter(self, tools, project_dir):
        result = tools["list_directory"].execute(path="packages/core", pattern="*.py")
        assert "main.py" in result
        # __init__.py should match too
        assert "__init__.py" in result

    def test_list_directory_hides_dotfiles(self, tools, project_dir):
        (project_dir / ".hidden").write_text("secret")
        result = tools["list_directory"].execute()
        assert ".hidden" not in result

    def test_list_directory_shows_gitignore(self, tools, project_dir):
        (project_dir / ".gitignore").write_text("*.pyc")
        result = tools["list_directory"].execute()
        assert ".gitignore" in result

    def test_search_skips_venv(self, tools, project_dir):
        venv = project_dir / ".venv" / "lib"
        venv.mkdir(parents=True)
        (venv / "site.py").write_text("venv_marker_string")
        result = tools["search_code"].execute(pattern="venv_marker_string", glob="**/*.py")
        assert "No matches found" in result

    def test_search_output_newline_joined(self, tools, project_dir):
        """Multiple search results are newline-separated."""
        (project_dir / "packages" / "core" / "other.py").write_text("line_one\nline_two\n")
        result = tools["search_code"].execute(pattern="line_")
        lines = [line for line in result.split("\n") if ":" in line]
        assert len(lines) == 2

    def test_search_no_match_includes_glob_in_message(self, tools):
        result = tools["search_code"].execute(pattern="zzz_nope", glob="*.txt")
        assert result == "No matches found for pattern 'zzz_nope' in '*.txt'."

    def test_search_truncation_message_format(self, tools, project_dir):
        lines = "\n".join(f"repeated_token_{i}" for i in range(100))
        (project_dir / "repeat.py").write_text(lines)
        result = tools["search_code"].execute(pattern="repeated_token", max_results=3)
        assert result.endswith("[Truncated at 3 results]")
