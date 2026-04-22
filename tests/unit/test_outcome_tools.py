"""Tests for packages.core.tools.outcome_tools."""

from pathlib import Path

from freezegun import freeze_time

from packages.core import frontmatter
from packages.core.filesystem_access import AccessLevel, AccessRule, FilesystemGuard
from packages.core.tools.outcome_tools import (
    _next_available_path,
    _slugify,
    make_outcome_tools,
)


def _guard_for(path: Path, access: AccessLevel = AccessLevel.READ_WRITE) -> FilesystemGuard:
    return FilesystemGuard([AccessRule(path=path.resolve(), access=access)])


# --- _slugify ---


def test_slugify_basic():
    assert _slugify("Migrate auth service off legacy middleware") == "migrate-auth-service-off-legacy-middleware"


def test_slugify_caps_at_max_words():
    assert _slugify("one two three four five six seven eight") == "one-two-three-four-five-six"


def test_slugify_strips_punctuation():
    assert _slugify("Hello, world! What's up?") == "hello-world-what-s-up"


def test_slugify_empty_returns_untitled():
    assert _slugify("") == "untitled"


def test_slugify_only_punctuation_returns_untitled():
    assert _slugify("!!! ???") == "untitled"


def test_slugify_collapses_multiple_dashes():
    assert _slugify("foo   bar - baz") == "foo-bar-baz"


# --- _next_available_path ---


def test_next_available_path_first_slot_free(tmp_path: Path):
    result = _next_available_path(tmp_path, "2026-04-18", "foo")
    assert result == tmp_path / "2026-04-18-foo.md"


def test_next_available_path_collision_appends_2(tmp_path: Path):
    (tmp_path / "2026-04-18-foo.md").write_text("x")
    result = _next_available_path(tmp_path, "2026-04-18", "foo")
    assert result == tmp_path / "2026-04-18-foo-2.md"


def test_next_available_path_multiple_collisions(tmp_path: Path):
    (tmp_path / "2026-04-18-foo.md").write_text("x")
    (tmp_path / "2026-04-18-foo-2.md").write_text("x")
    (tmp_path / "2026-04-18-foo-3.md").write_text("x")
    result = _next_available_path(tmp_path, "2026-04-18", "foo")
    assert result == tmp_path / "2026-04-18-foo-4.md"


# --- track_recommendation tool ---


@freeze_time("2026-04-18 14:32:00")
def test_track_recommendation_writes_file(tmp_path: Path):
    tools = make_outcome_tools(tmp_path, _guard_for(tmp_path), "2026-04-18-143200")
    assert len(tools) == 1
    tool = tools[0]
    assert tool.name == "track_recommendation"

    result = tool.execute(
        what="Migrate auth service off legacy middleware",
        why="Legal flagged session token storage for compliance",
        revisit_in="1 month",
        success_looks_like="Zero rollback, all prod traffic on new middleware",
    )

    expected_file = tmp_path / "2026-04-18-migrate-auth-service-off-legacy-middleware.md"
    assert expected_file.exists()
    assert result == "Tracked: 'Migrate auth service off legacy middleware' — revisit 2026-05-18"


@freeze_time("2026-04-18 14:32:00")
def test_track_recommendation_frontmatter_contents(tmp_path: Path):
    tools = make_outcome_tools(tmp_path, _guard_for(tmp_path), "2026-04-18-143200")
    tool = tools[0]
    tool.execute(
        what="Switch to Postgres",
        why="Scale concerns",
        revisit_in="2 weeks",
    )
    written = (tmp_path / "2026-04-18-switch-to-postgres.md").read_text(encoding="utf-8")
    meta, body = frontmatter.parse(written)

    assert meta["created_at"] == "2026-04-18T14:32:00"
    assert meta["revisit_at"] == "2026-05-02"
    assert meta["status"] == "pending"
    assert meta["what"] == "Switch to Postgres"
    assert meta["why"] == "Scale concerns"
    assert meta["success_looks_like"] == ""
    assert meta["conversation_id"] == "2026-04-18-143200"
    assert body == ""


@freeze_time("2026-04-18 14:32:00")
def test_track_recommendation_preserves_key_order(tmp_path: Path):
    tools = make_outcome_tools(tmp_path, _guard_for(tmp_path), "c1")
    tools[0].execute(what="A", why="B", revisit_in="1 day")
    written = (tmp_path / "2026-04-18-a.md").read_text(encoding="utf-8")
    lines = written.splitlines()
    key_order = [line.split(":")[0] for line in lines if ":" in line and not line.startswith("---")]
    assert key_order == [
        "created_at",
        "revisit_at",
        "status",
        "what",
        "why",
        "success_looks_like",
        "conversation_id",
    ]


@freeze_time("2026-04-18 14:32:00")
def test_track_recommendation_handles_collision(tmp_path: Path):
    tools = make_outcome_tools(tmp_path, _guard_for(tmp_path), "c1")
    tool = tools[0]
    tool.execute(what="Same thing", why="one", revisit_in="1 day")
    tool.execute(what="Same thing", why="two", revisit_in="1 day")

    assert (tmp_path / "2026-04-18-same-thing.md").exists()
    assert (tmp_path / "2026-04-18-same-thing-2.md").exists()


@freeze_time("2026-04-18 14:32:00")
def test_track_recommendation_rejected_by_fs_guard(tmp_path: Path):
    # Guard with no rules → denies everything
    empty_guard = FilesystemGuard([])
    tools = make_outcome_tools(tmp_path, empty_guard, "c1")
    result = tools[0].execute(what="X", why="Y", revisit_in="1 day")

    assert result.startswith("Error: filesystem guard denies write access")
    assert list(tmp_path.iterdir()) == []


@freeze_time("2026-04-18 14:32:00")
def test_track_recommendation_invalid_date_returns_error(tmp_path: Path):
    tools = make_outcome_tools(tmp_path, _guard_for(tmp_path), "c1")
    result = tools[0].execute(what="X", why="Y", revisit_in="eventually")

    assert result.startswith("Error:")
    assert "eventually" in result
    assert list(tmp_path.iterdir()) == []


@freeze_time("2026-04-18 14:32:00")
def test_track_recommendation_truncates_long_what_in_confirmation(tmp_path: Path):
    tools = make_outcome_tools(tmp_path, _guard_for(tmp_path), "c1")
    long_what = "x" * 200
    result = tools[0].execute(what=long_what, why="Y", revisit_in="1 day")

    assert "..." in result
    # Truncated confirmation is ≤ 80 chars of content + ellipsis; file body is untruncated
    written_meta, _ = frontmatter.parse(next(iter(tmp_path.iterdir())).read_text())
    assert written_meta["what"] == long_what


@freeze_time("2026-04-18 14:32:00")
def test_track_recommendation_tool_schema(tmp_path: Path):
    tools = make_outcome_tools(tmp_path, _guard_for(tmp_path), "c1")
    tool = tools[0]

    assert tool.parameters["type"] == "object"
    assert set(tool.parameters["required"]) == {"what", "why", "revisit_in"}
    assert set(tool.parameters["properties"].keys()) == {
        "what",
        "why",
        "revisit_in",
        "success_looks_like",
    }


def test_track_recommendation_uses_iso_date_input(tmp_path: Path):
    with freeze_time("2026-04-18 14:32:00"):
        tools = make_outcome_tools(tmp_path, _guard_for(tmp_path), "c1")
        tools[0].execute(what="X", why="Y", revisit_in="2026-09-01")
    meta, _ = frontmatter.parse((tmp_path / "2026-04-18-x.md").read_text(encoding="utf-8"))
    assert meta["revisit_at"] == "2026-09-01"
