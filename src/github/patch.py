"""Pure saved-PR unified patch reconstruction; no network access."""

import re


_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def _restore_old_code(current_code: str, patch: str) -> str:
    """Reverse the saved PR patch against its original head, not the rebased tip."""
    current_lines = current_code.splitlines(keepends=True)
    patch_lines = patch.splitlines()
    restored = []
    cursor = index = hunks = 0
    while index < len(patch_lines):
        match = _HUNK.match(patch_lines[index])
        if not match:
            raise ValueError("Missing or unsupported PR patch; refusing incomplete code context")
        hunks += 1
        old_count = int(match[2]) if match[2] is not None else 1
        new_count = int(match[4]) if match[4] is not None else 1
        start = int(match[3]) - (1 if new_count else 0)
        if not cursor <= start <= len(current_lines):
            raise ValueError("PR patch hunk does not match the original source file")
        restored.extend(current_lines[cursor:start])
        cursor = start
        seen_old = seen_new = 0
        previous_kind = None
        index += 1
        while index < len(patch_lines) and not patch_lines[index].startswith("@@"):
            line = patch_lines[index]
            if line == "\\ No newline at end of file":
                if previous_kind == "-":
                    restored[-1] = restored[-1].removesuffix("\n")
                index += 1
                continue
            if not line or line[0] not in " +-":
                raise ValueError("Unsupported line in saved PR patch")
            kind, text = line[0], line[1:]
            if kind in " +":
                if cursor >= len(current_lines) or current_lines[cursor].rstrip("\r\n") != text:
                    raise ValueError("PR patch does not match the original source file")
                if kind == " ":
                    restored.append(current_lines[cursor])
                cursor += 1
                seen_new += 1
            if kind == "-":
                restored.append(text + "\n")
            if kind in " -":
                seen_old += 1
            previous_kind = kind
            index += 1
        if (seen_old, seen_new) != (old_count, new_count):
            raise ValueError("Truncated PR patch; refusing incomplete code context")
    if not hunks:
        raise ValueError("No text patch was available for the changed file")
    restored.extend(current_lines[cursor:])
    return "".join(restored)


