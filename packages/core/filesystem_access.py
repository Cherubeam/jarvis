"""
General-purpose filesystem access control layer.

Provides per-path permission rules (read, write, read-write, deny)
with most-specific-path-wins resolution. Default: deny.

Not Obsidian-specific — reusable for any filesystem gating.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class AccessLevel(Enum):
    DENY = "deny"
    READ = "read"
    WRITE = "write"
    READ_WRITE = "read-write"


@dataclass(frozen=True)
class AccessRule:
    """A single access rule mapping an absolute path to a permission level."""

    path: Path
    access: AccessLevel


class FilesystemGuard:
    """Enforces per-path access control using most-specific-path-wins resolution.

    Rules are sorted by path depth (deepest first). The first matching rule
    determines access. No match defaults to deny.
    """

    def __init__(self, rules: list[AccessRule]) -> None:
        # Sort by path depth descending (most specific first)
        self._rules = sorted(rules, key=lambda r: len(r.path.parts), reverse=True)

    @property
    def rules(self) -> list[AccessRule]:
        return list(self._rules)

    def _resolve_access(self, path: Path) -> AccessLevel | None:
        """Find the most specific rule matching the given path."""
        resolved = path.resolve()
        for rule in self._rules:
            try:
                resolved.relative_to(rule.path)
                return rule.access
            except ValueError:
                continue
        return None

    def check_read(self, path: Path) -> bool:
        """Check whether read access is allowed for the given path."""
        access = self._resolve_access(path)
        if access is None:
            return False
        return access in (AccessLevel.READ, AccessLevel.READ_WRITE)

    def check_write(self, path: Path) -> bool:
        """Check whether write access is allowed for the given path."""
        access = self._resolve_access(path)
        if access is None:
            return False
        return access in (AccessLevel.WRITE, AccessLevel.READ_WRITE)


def load_filesystem_guard(config: dict) -> FilesystemGuard:
    """Build a FilesystemGuard from config dictionary.

    Expected config shape:
        filesystem:
          access_rules:
            - path: "~/some/path"
              access: read
    """
    fs_config = config.get("filesystem", {})
    raw_rules = fs_config.get("access_rules", [])

    rules: list[AccessRule] = []
    for entry in raw_rules:
        raw_path = entry.get("path", "")
        raw_access = entry.get("access", "deny")

        path = Path(raw_path).expanduser().resolve()
        try:
            access = AccessLevel(raw_access)
        except ValueError:
            logger.warning(
                f"Unknown access level '{raw_access}' for {raw_path}, defaulting to deny"
            )
            access = AccessLevel.DENY

        rules.append(AccessRule(path=path, access=access))

    return FilesystemGuard(rules)
