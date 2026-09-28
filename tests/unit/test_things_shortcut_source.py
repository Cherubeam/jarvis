"""Tests for the Things export Shortcut runner (subprocess and platform mocked; runs on Linux CI)."""

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from packages.integrations.things3.shortcut_source import SHORTCUT_NAME, ThingsUnavailableError, run_export

MOD = "packages.integrations.things3.shortcut_source"


def _fake_run(payload=None, *, returncode=0, stderr="", as_dir=False, write=True):
    """Stand-in for subprocess.run that writes what `shortcuts run -o <path>` would."""

    def run(cmd, **kwargs):
        out = Path(cmd[cmd.index("--output-path") + 1])
        if write and returncode == 0:
            if as_dir:
                out.mkdir()
                (out / "item.txt").write_text("{}")
            else:
                out.write_text(payload if isinstance(payload, str) else json.dumps(payload))
        return subprocess.CompletedProcess(cmd, returncode, stdout="", stderr=stderr)

    return run


@pytest.fixture
def on_mac():
    with patch(f"{MOD}.sys.platform", "darwin"), patch(f"{MOD}.shutil.which", return_value="/usr/bin/shortcuts"):
        yield


@pytest.mark.unit
class TestRunExport:
    def test_valid_export(self, on_mac):
        export = {"inbox": [{"id": "a"}], "scheduled": [{"id": "b"}]}
        with patch(f"{MOD}.subprocess.run", side_effect=_fake_run(export)) as run:
            assert run_export() == export
        cmd = run.call_args[0][0]
        assert cmd[:3] == ["shortcuts", "run", SHORTCUT_NAME]
        assert cmd[cmd.index("--output-type") + 1] == "public.json"
        assert run.call_args.kwargs["timeout"] == 10

    def test_missing_key_becomes_empty_list(self, on_mac):
        with patch(f"{MOD}.subprocess.run", side_effect=_fake_run({"inbox": []})):
            assert run_export() == {"inbox": [], "scheduled": []}

    def test_not_macos(self):
        with patch(f"{MOD}.sys.platform", "linux"), pytest.raises(ThingsUnavailableError, match="needs macOS"):
            run_export()

    def test_no_shortcuts_cli(self):
        with (
            patch(f"{MOD}.sys.platform", "darwin"),
            patch(f"{MOD}.shutil.which", return_value=None),
            pytest.raises(ThingsUnavailableError, match="'shortcuts' command"),
        ):
            run_export()

    def test_shortcut_fails(self, on_mac):
        run = _fake_run(returncode=1, stderr="Error: The shortcut “JARVIS Things Export” couldn’t be found.\n")
        with (
            patch(f"{MOD}.subprocess.run", side_effect=run),
            pytest.raises(ThingsUnavailableError, match="couldn’t be found"),
        ):
            run_export()

    def test_timeout(self, on_mac):
        timeout = subprocess.TimeoutExpired(cmd="shortcuts", timeout=10)
        with (
            patch(f"{MOD}.subprocess.run", side_effect=timeout),
            pytest.raises(ThingsUnavailableError, match="within 10s"),
        ):
            run_export()

    def test_list_output_is_rejected(self, on_mac):
        with (
            patch(f"{MOD}.subprocess.run", side_effect=_fake_run(as_dir=True)),
            pytest.raises(ThingsUnavailableError, match="one dictionary, not a list"),
        ):
            run_export()

    def test_no_output(self, on_mac):
        with (
            patch(f"{MOD}.subprocess.run", side_effect=_fake_run(write=False)),
            pytest.raises(ThingsUnavailableError, match="produced no output"),
        ):
            run_export()

    def test_invalid_json(self, on_mac):
        with (
            patch(f"{MOD}.subprocess.run", side_effect=_fake_run("not json")),
            pytest.raises(ThingsUnavailableError, match="isn't JSON"),
        ):
            run_export()

    @pytest.mark.parametrize("payload", [[1, 2], {"inbox": "text"}, {"scheduled": [1]}])
    def test_wrong_shape(self, on_mac, payload):
        with patch(f"{MOD}.subprocess.run", side_effect=_fake_run(payload)), pytest.raises(ThingsUnavailableError):
            run_export()
