# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Helpers for selecting psort time-slice files in downstream tasks.

When time-slicing is enabled, the plaso psort worker splits its output into
several files. Each file's display_name records which slice it is, using the
pattern ``<base>.slice-<number>-of-<total>.<ext>`` (for example
``timeline.slice-2-of-5.jsonl``). Downstream exporters (Splunk, S3,
Timesketch) often want to upload only some of those slices, so this module
provides the parser and selector used to pick them.
"""

import re
from typing import Union

# Matches the ".slice-<number>-of-<total>." marker anywhere in a display_name.
_SLICE_RE = re.compile(r"\.slice-(\d+)-of-(\d+)\.")


def parse_slice_index(display_name: str) -> tuple[int, int] | None:
    """Reads the slice marker from a file's display name.

    Args:
        display_name: The file's display name, which may contain a
            ``.slice-<number>-of-<total>.`` marker.

    Returns:
        A ``(slice_number, total_slices)`` tuple if the name has a slice
        marker, otherwise None.
    """
    if not display_name:
        return None
    match = _SLICE_RE.search(display_name)
    return (int(match.group(1)), int(match.group(2))) if match else None


def _normalize_mode(mode: Union[str, int, None]) -> Union[str, int]:
    """Validates and normalizes a slice-selection mode.

    Args:
        mode: The selection mode. Accepts "all", "latest", a positive
            integer (or its string form), None, or an empty string.

    Returns:
        "all", "latest", or a positive integer.

    Raises:
        ValueError: If mode is a boolean, a non-integer, or an integer
            less than 1.
    """
    if mode is None or mode == "" or mode == "all":
        return "all"
    if mode == "latest":
        return "latest"
    if isinstance(mode, bool):
        # bool is an int subclass; reject explicitly so True/False don't
        # silently become slice index 1/0.
        raise ValueError(
            f"slice_select must be 'all', 'latest', or a positive integer; got {mode!r}"
        )
    try:
        value = int(mode)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"slice_select must be 'all', 'latest', or a positive integer; got {mode!r}"
        ) from exc
    if value < 1:
        raise ValueError(f"slice_select index must be >= 1; got {value}")
    return value


def select_slice(
    input_files: list[dict], mode: Union[str, int, None] = "all"
) -> list[dict]:
    """Picks which time-slice files to keep from a list of input files.

    Files that don't have a slice marker in their display name always pass
    through unchanged, so unrelated inputs in a mixed pipeline are never
    dropped.

    Args:
        input_files: A list of OutputFile-style dicts, each with a
            "display_name" key.
        mode: Which slices to keep:
            "all" (default) keeps every file;
            "latest" keeps only the last slice of each file (the most
            recent time window);
            a positive integer keeps only that slice number.

    Returns:
        The filtered list of input files.

    Raises:
        ValueError: If mode is invalid (see _normalize_mode), or if mode is
            a slice number higher than a file's total number of slices.
    """
    normalized = _normalize_mode(mode)
    if normalized == "all":
        return list(input_files)

    selected: list[dict] = []
    for f in input_files:
        parsed = parse_slice_index(f.get("display_name", ""))
        if parsed is None:
            selected.append(f)
            continue
        slice_number, total_slices = parsed
        if normalized == "latest":
            if slice_number == total_slices:
                selected.append(f)
        else:  # specific slice number
            if normalized > total_slices:
                raise ValueError(
                    f"slice_select={normalized} is out of range for "
                    f"{f.get('display_name')!r} (only {total_slices} slices available)"
                )
            if slice_number == normalized:
                selected.append(f)
    return selected
