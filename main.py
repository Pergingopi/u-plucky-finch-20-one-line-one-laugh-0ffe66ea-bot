#!/usr/bin/env python3
"""One Line, One Laugh — make.fun entry.

Writes a single funny line (1-200 characters) to
$MAKEFUN_OUTPUT_DIR/entry.txt (default /output/entry.txt).

The output directory itself is never deleted: the grader mounts it, so
only a staging file inside it is created and atomically renamed into
place. The published file is chmod 0644 so the grader (a different
user) can read it.
"""

import os
import sys
import tempfile
import unicodedata

ENTRY_LINE = "I asked the void for a sign, and it replied 'seen 3:42 AM'."

MAX_CHARS = 200
TARGET_NAME = "entry.txt"
PUBLISH_MODE = 0o644

# Characters the gate rejects outright, each with its own message.
_FORBIDDEN_SINGLE = {
    "\ufeff": "byte-order mark (U+FEFF)",
    "\u2028": "line separator (U+2028)",
    "\u2029": "paragraph separator (U+2029)",
}


def check_shape(text):
    """Reject empty, whitespace-only, over-long, or multi-line text."""
    if not isinstance(text, str):
        raise ValueError("entry must be a str")
    if text == "":
        raise ValueError("entry is empty")
    if text.strip() == "":
        raise ValueError("entry is whitespace-only")
    if len(text) > MAX_CHARS:
        raise ValueError(
            "entry is %d chars, over the %d limit" % (len(text), MAX_CHARS)
        )
    if "\n" in text or "\r" in text:
        raise ValueError("entry must be a single line")
    return text


def check_characters(text):
    """Reject BOM, C1 controls, and invisible control/format characters."""
    for ch in text:
        cp = ord(ch)
        label = _FORBIDDEN_SINGLE.get(ch)
        if label is not None:
            raise ValueError("entry contains a %s" % label)
        if 0x0080 <= cp <= 0x009F:
            raise ValueError("entry contains a C1 control character U+%04X" % cp)
        if unicodedata.category(ch) in ("Cc", "Cf", "Cs"):
            raise ValueError(
                "entry contains an invisible control/format/surrogate "
                "character U+%04X" % cp
            )
    return text


def validate_entry(text):
    """Run every gate check; returns the text unchanged on success."""
    return check_characters(check_shape(text))


def publish_entry(out_dir, data):
    """Atomically stage + rename data into out_dir/entry.txt, mode 0644.

    Returns the target path. The staging file lives inside out_dir so
    the rename never crosses filesystems (the grader bind-mounts the
    output dir; a rename from /tmp would fail with EXDEV).
    """
    fd, tmp_path = tempfile.mkstemp(
        dir=out_dir, prefix=".entry.txt.", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp_path, PUBLISH_MODE)
        target = os.path.join(out_dir, TARGET_NAME)
        os.replace(tmp_path, target)
        # fsync the directory so the rename is durable.
        dir_fd = os.open(out_dir, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
        return target
    finally:
        # os.replace already moved the staging file on success; this
        # only cleans up after a failure mid-publish.
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def verify_published(target, data):
    """Read-back check: bytes, mode, and a final gate validation."""
    with open(target, "rb") as f:
        read_back = f.read()
    if read_back != data:
        raise ValueError("read-back mismatch after publish")
    if (os.stat(target).st_mode & 0o777) != PUBLISH_MODE:
        raise ValueError("entry.txt is not mode 0644")
    try:
        text = read_back.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("entry.txt is not valid UTF-8: %s" % exc)
    validate_entry(text)


def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR") or "/output"
    if os.path.exists(out_dir) and not os.path.isdir(out_dir):
        raise ValueError("output path %r is a file, not a directory" % out_dir)
    os.makedirs(out_dir, exist_ok=True)

    line = validate_entry(ENTRY_LINE)
    data = line.encode("utf-8")

    target = publish_entry(out_dir, data)
    verify_published(target, data)

    print("wrote %s (%d chars)" % (target, len(line)))
    print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
