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
"""Tests for openrelik_worker_common.slice_utils."""

import pytest

from openrelik_worker_common.slice_utils import parse_slice_index, select_slice


def _f(name):
    return {"display_name": name, "path": f"/tmp/{name}"}


class TestParseSliceIndex:
    def test_canonical_pattern(self):
        assert parse_slice_index("foo.plaso.slice-2-of-4.jsonl") == (2, 4)

    def test_double_digit(self):
        assert parse_slice_index("a.slice-12-of-12.csv") == (12, 12)

    def test_no_suffix(self):
        assert parse_slice_index("foo.plaso.jsonl") is None

    def test_empty(self):
        assert parse_slice_index("") is None
        assert parse_slice_index(None) is None

    def test_almost_match_rejected(self):
        # Missing trailing dot — not a slice marker, just a base name.
        assert parse_slice_index("evidence.slice-2-of-4") is None
        # Wrong delimiter.
        assert parse_slice_index("evidence.slice_2_of_4.jsonl") is None


class TestSelectSlice:
    def setup_method(self):
        self.three = [
            _f("foo.plaso.slice-1-of-3.csv"),
            _f("foo.plaso.slice-2-of-3.csv"),
            _f("foo.plaso.slice-3-of-3.csv"),
        ]

    def test_default_all_is_identity(self):
        assert select_slice(self.three) == self.three

    def test_explicit_all(self):
        assert select_slice(self.three, mode="all") == self.three

    def test_none_mode_is_all(self):
        assert select_slice(self.three, mode=None) == self.three

    def test_empty_string_mode_is_all(self):
        assert select_slice(self.three, mode="") == self.three

    def test_latest_keeps_highest_index(self):
        result = select_slice(self.three, mode="latest")
        assert [f["display_name"] for f in result] == [
            "foo.plaso.slice-3-of-3.csv"
        ]

    def test_int_index_picks_specific_slice(self):
        result = select_slice(self.three, mode=2)
        assert [f["display_name"] for f in result] == [
            "foo.plaso.slice-2-of-3.csv"
        ]

    def test_string_int_index_works(self):
        result = select_slice(self.three, mode="2")
        assert [f["display_name"] for f in result] == [
            "foo.plaso.slice-2-of-3.csv"
        ]

    def test_zero_index_raises(self):
        with pytest.raises(ValueError, match=">= 1"):
            select_slice(self.three, mode=0)

    def test_negative_index_raises(self):
        with pytest.raises(ValueError, match=">= 1"):
            select_slice(self.three, mode="-1")

    def test_out_of_range_raises(self):
        with pytest.raises(ValueError, match="out of range"):
            select_slice(self.three, mode=4)

    def test_unparseable_mode_raises(self):
        with pytest.raises(ValueError, match="must be 'all'"):
            select_slice(self.three, mode="bogus")

    def test_bool_mode_rejected(self):
        with pytest.raises(ValueError, match="must be 'all'"):
            select_slice(self.three, mode=True)

    def test_non_slice_input_passes_through(self):
        files = [_f("foo.plaso.jsonl"), _f("bar.csv")]
        assert select_slice(files, mode="latest") == files
        assert select_slice(files, mode=1) == files

    def test_mixed_slice_and_non_slice(self):
        mixed = self.three + [_f("unrelated.txt")]
        result = select_slice(mixed, mode="latest")
        names = [f["display_name"] for f in result]
        assert "unrelated.txt" in names
        assert "foo.plaso.slice-3-of-3.csv" in names
        assert "foo.plaso.slice-1-of-3.csv" not in names

    def test_multi_family_latest_picks_one_per_family(self):
        # Two distinct upstream sources, each with its own slice family.
        files = [
            _f("a.plaso.slice-1-of-2.csv"),
            _f("a.plaso.slice-2-of-2.csv"),
            _f("b.plaso.slice-1-of-2.csv"),
            _f("b.plaso.slice-2-of-2.csv"),
        ]
        result = select_slice(files, mode="latest")
        names = sorted(f["display_name"] for f in result)
        assert names == [
            "a.plaso.slice-2-of-2.csv",
            "b.plaso.slice-2-of-2.csv",
        ]

    def test_preserves_order_for_passthrough(self):
        # Non-slice files should be returned in original order.
        files = [_f("z.txt"), _f("a.txt"), _f("foo.slice-1-of-1.csv")]
        result = select_slice(files, mode="latest")
        names = [f["display_name"] for f in result]
        # z, a stay in input order; the slice-1-of-1 is also "latest".
        assert names == ["z.txt", "a.txt", "foo.slice-1-of-1.csv"]
