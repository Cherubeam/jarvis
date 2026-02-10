"""
Callout block parser for Obsidian > [!JARVIS] blocks.

Pure string operations — no filesystem I/O. Handles parsing and
manipulation of JARVIS callout blocks in Obsidian markdown files.
"""

from dataclasses import dataclass


@dataclass
class CalloutBlock:
    """A parsed > [!JARVIS] callout block."""

    start_line: int  # 0-indexed line of "> [!JARVIS]"
    end_line: int  # 0-indexed last line of the block
    existing_content: str  # Content inside block (without > prefix)


@dataclass
class CalloutNotFound:
    """Sentinel indicating no JARVIS callout was found."""

    pass


def find_jarvis_callout(content: str) -> CalloutBlock | CalloutNotFound:
    """Find the > [!JARVIS] callout block in markdown content.

    The block starts at a line matching "> [!JARVIS]" (case-insensitive
    for the tag) and continues while subsequent lines start with "> "
    or are empty/whitespace-only lines within the block.

    Returns CalloutBlock with parsed data, or CalloutNotFound.
    """
    lines = content.split("\n")
    start_line = None

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.lower().startswith("> [!jarvis]"):
            start_line = i
            break

    if start_line is None:
        return CalloutNotFound()

    # Walk forward to find the end of the callout block.
    # Block continues while lines start with ">" or are blank
    # (blank lines within a callout are still part of it if followed
    # by more ">" lines). We stop at the first non-blank, non-">" line.
    end_line = start_line
    content_lines: list[str] = []

    # Skip the header line itself — collect content from next line
    i = start_line + 1
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith(">"):
            # Part of the callout — extract content after "> "
            text = stripped[1:].lstrip() if len(stripped) > 1 else ""
            content_lines.append(text)
            end_line = i
            i += 1
        elif stripped == "":
            # Blank line — check if there are more ">" lines after it
            # (blank lines inside callouts are allowed)
            j = i + 1
            while j < len(lines) and lines[j].strip() == "":
                j += 1
            if j < len(lines) and lines[j].strip().startswith(">"):
                content_lines.append("")
                end_line = i
                i += 1
            else:
                # Blank line followed by non-callout content — block ends
                break
        else:
            # Non-callout, non-blank line — block ends
            break

    existing_content = "\n".join(content_lines)

    return CalloutBlock(
        start_line=start_line,
        end_line=end_line,
        existing_content=existing_content,
    )


def format_callout_entry(text: str) -> str:
    """Format text as callout lines with > prefix.

    Each line gets prefixed with "> ".
    """
    lines = text.split("\n")
    return "\n".join(f"> {line}" if line.strip() else ">" for line in lines)


def build_updated_content(
    original: str, callout: CalloutBlock, new_entry: str
) -> str:
    """Build the full file content with new_entry appended inside the callout.

    Inserts the new entry at the end of the existing callout block.
    """
    lines = original.split("\n")

    # Format the new entry as callout lines
    formatted_entry = format_callout_entry(new_entry)

    # Build new content: everything up to end_line, then new entry, then rest
    before = lines[: callout.end_line + 1]
    after = lines[callout.end_line + 1 :]

    # Add a blank callout line separator if there's existing content
    if callout.existing_content.strip():
        separator = [">"]
    else:
        separator = []

    new_lines = before + separator + formatted_entry.split("\n") + after

    return "\n".join(new_lines)
