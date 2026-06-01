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

The plaso psort worker can split its output into N files whose display_name
encodes the slice index: ``<base>.slice-<K>-of-<N>.<ext>``. Downstream
exporters (Splunk, S3, Timesketch) often want to scope which slices they
ingest. This module provides the parser + selector so the rule lives in one
place.
"""

import re
from typing import Union

# Matches ".slice-<K>-of-<N>." anywhere in display_name.
_SLICE_RE = re.compile(r"\.slice-(\d+)-of-(\d+)\.")


def parse_slice_index(display_name: str) -> tuple[int, int] | None:
    """Return ``(k, n)`` if ``display_name`` carries a psort slice suffix,
    else ``None``."""
    if not display_name:
        return None
    match = _SLICE_RE.search(display_name)
    return (int(match.group(1)), int(match.group(2))) if match else None


def _normalize_mode(mode: Union[str, int, None]) -> Union[str, int]:
    """Coerce mode into ``"all"``, ``"latest"``, or a positive int. Raises
    ``ValueError`` for anything else."""
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
    """Filter a list of OutputFile-style dicts by slice membership.

    ``mode`` accepts:
      * ``"all"`` (default) — return ``input_files`` unchanged.
      * ``"latest"`` — keep only the file whose K equals N (the newest
        slice). Files without a slice suffix pass through unchanged.
      * positive int K — keep only files whose slice index equals K. Raises
        ``ValueError`` if a file's family has fewer than K slices.

    Files without a ``slice-K-of-N`` suffix always pass through, so mixed
    pipelines don't silently drop unrelated inputs.
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
        k, n = parsed
        if normalized == "latest":
            if k == n:
                selected.append(f)
        else:  # positive int
            if normalized > n:
                raise ValueError(
                    f"slice_select={normalized} is out of range for "
                    f"{f.get('display_name')!r} (only {n} slices available)"
                )
            if k == normalized:
                selected.append(f)
    return selected
