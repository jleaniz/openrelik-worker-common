import os
import tempfile
import unittest
from unittest.mock import patch

from openrelik_worker_common.archive_utils import extract_archive


class TestArchiveUtils(unittest.TestCase):
    output_folder = "/tmp"
    log_file = "/tmp/log.txt"
    file_filter = ["*.txt", "*.evtx"]

    @patch("subprocess.call")
    @patch("subprocess.check_output")
    @patch("shutil.which")
    def test_extract_archive_tgz(
        self, mock_which, mock_check_output, mock_subprocess_call
    ):
        input_file = {"path": "/path/to/archive.tgz", "display_name": "archive.tgz"}
        mock_check_output.return_value = b""
        mock_which.return_value = True
        mock_subprocess_call.return_value = 0

        result = extract_archive(
            input_file, self.output_folder, self.log_file, self.file_filter
        )
        self.assertIn("tar -vxzf", result[0])
        self.assertIn("*.txt", result[0])
        self.assertIn(self.output_folder, result[1])

    @patch("subprocess.call")
    @patch("subprocess.check_output")
    @patch("shutil.which")
    def test_extract_archive_tgz_no_filter(
        self, mock_which, mock_check_output, mock_subprocess_call
    ):
        input_file = {"path": "/path/to/archive.tgz", "display_name": "archive.tgz"}
        mock_check_output.return_value = b""
        mock_which.return_value = True
        mock_subprocess_call.return_value = 0

        result = extract_archive(input_file, self.output_folder, self.log_file)
        self.assertIn("tar -vxzf", result[0])
        self.assertNotIn("--wildcards", result[0])
        self.assertIn(self.output_folder, result[1])

    @patch("subprocess.call")
    @patch("subprocess.check_output")
    @patch("shutil.which")
    def test_extract_archive_zip(
        self, mock_which, mock_check_output, mock_subprocess_call
    ):
        input_file = {"path": "/path/to/archive.zip", "display_name": "archive.zip"}
        mock_check_output.return_value = b""
        mock_which.return_value = True
        mock_subprocess_call.return_value = 0

        result = extract_archive(
            input_file, self.output_folder, self.log_file, self.file_filter
        )
        self.assertIn("7z x", result[0])
        self.assertIn("*.txt", result[0])
        self.assertIn(self.output_folder, result[1])

    @patch("subprocess.call")
    @patch("subprocess.check_output")
    @patch("shutil.which")
    def test_extract_archive_tar_includes_password(
        self, mock_which, mock_check_output, mock_subprocess_call
    ):
        input_file = {"path": "/path/to/archive.tar.gz", "display_name": "archive.tar.gz"}
        mock_check_output.return_value = b""
        mock_which.return_value = True
        mock_subprocess_call.return_value = 0

        result = extract_archive(
            input_file, self.output_folder, self.log_file, self.file_filter, "Openrelik123!"
        )
        self.assertIn("tar -vxzf", result[0])
        self.assertNotIn("-pOpenrelik123!", result[0])
        self.assertIn(self.output_folder, result[1])

    @patch("subprocess.call")
    @patch("subprocess.check_output")
    @patch("shutil.which")
    def test_extract_archive_zip_includes_password(
        self, mock_which, mock_check_output, mock_subprocess_call
    ):
        input_file = {"path": "/path/to/archive.zip", "display_name": "archive.zip"}
        mock_check_output.return_value = b""
        mock_which.return_value = True
        mock_subprocess_call.return_value = 0

        result = extract_archive(
            input_file, self.output_folder, self.log_file, self.file_filter, "Openrelik123!"
        )
        self.assertIn("7z x", result[0])
        self.assertIn("*.txt", result[0])
        self.assertIn("-pOpenrelik123!", result[0])
        self.assertIn(self.output_folder, result[1])

    @patch("subprocess.call")
    @patch("subprocess.check_output")
    @patch("shutil.which")
    def test_extract_archive_zip_no_filter(
        self, mock_which, mock_check_output, mock_subprocess_call
    ):
        input_file = {"path": "/path/to/archive.zip", "display_name": "archive.zip"}
        mock_check_output.return_value = b""
        mock_which.return_value = True
        mock_subprocess_call.return_value = 0

        result = extract_archive(input_file, self.output_folder, self.log_file)
        self.assertIn("7z x", result[0])
        self.assertNotIn("-r", result[0])
        self.assertIn(self.output_folder, result[1])

    @patch("subprocess.call")
    @patch("subprocess.check_output")
    @patch("shutil.which")
    def test_extract_archive_exit_1_is_warning_not_failure(
        self, mock_which, mock_check_output, mock_subprocess_call
    ):
        """7z exit 1 = warnings (e.g. skipped entries); must not raise."""
        input_file = {"path": "/path/to/archive.zip", "display_name": "archive.zip"}
        mock_which.return_value = True
        mock_check_output.return_value = b""
        mock_subprocess_call.return_value = 1

        cmd, export_folder = extract_archive(
            input_file, self.output_folder, self.log_file, self.file_filter
        )

        # Returned cleanly; downstream walks export_folder for whatever did extract.
        self.assertIn("7z x", cmd)
        self.assertIn(self.output_folder, export_folder)

    @patch("subprocess.call")
    @patch("shutil.which")
    def test_extract_archive_exit_2_with_no_output_raises(
        self, mock_which, mock_subprocess_call
    ):
        """Exit >= 2 AND empty export folder => truly broken archive, raise."""
        input_file = {"path": "/path/to/archive.zip", "display_name": "archive.zip"}
        mock_which.return_value = True
        mock_subprocess_call.return_value = 2
        # Default behavior: real os.makedirs runs, dir is empty.
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(RuntimeError):
                extract_archive(
                    input_file,
                    tmp,
                    os.path.join(tmp, "log.txt"),
                    self.file_filter,
                )

    @patch("subprocess.call")
    @patch("shutil.which")
    def test_extract_archive_exit_2_with_partial_output_is_warning(
        self, mock_which, mock_subprocess_call
    ):
        """Exit >= 2 but *something* extracted => treat as partial success."""
        input_file = {"path": "/path/to/archive.zip", "display_name": "archive.zip"}
        mock_which.return_value = True

        with tempfile.TemporaryDirectory() as tmp:
            # Simulate 7z writing at least one file into the export dir before
            # erroring out on a different entry. The export dir name is
            # uuid4()-generated, so we intercept os.makedirs to capture it
            # and drop a file there.
            created_dirs = []
            real_makedirs = os.makedirs

            def fake_makedirs(p, *a, **kw):
                real_makedirs(p, *a, **kw)
                created_dirs.append(p)

            def fake_call(*args, **kwargs):
                # Drop a fake "extracted" file into the newest created dir.
                assert created_dirs, "export dir not yet created"
                with open(os.path.join(created_dirs[-1], "some_file.txt"), "w") as f:
                    f.write("partial output")
                return 2

            mock_subprocess_call.side_effect = fake_call
            with patch("os.makedirs", side_effect=fake_makedirs):
                cmd, export_folder = extract_archive(
                    input_file,
                    tmp,
                    os.path.join(tmp, "log.txt"),
                    self.file_filter,
                )

            # No exception -> partial success accepted.
            self.assertTrue(os.path.exists(os.path.join(export_folder, "some_file.txt")))

    @patch("subprocess.check_output")
    def test_extract_archive_7z_not_found(self, mock_check_output):
        input_file = {"path": "/path/to/archive.tgz", "display_name": "archive.tgz"}
        mock_check_output.return_value = b""

        with patch("shutil.which", return_value=None):
            with self.assertRaises(RuntimeError):
                extract_archive(
                    input_file, self.output_folder, self.log_file, self.file_filter
                )

    @patch("os.makedirs")
    @patch("shutil.which")
    def test_extract_archive_mkdir_error(self, mock_which, mock_makedirs):
        input_file = {"path": "/path/to/archive.tgz", "display_name": "archive.tgz"}
        mock_makedirs.side_effect = OSError("Mocked error")
        mock_which.return_value = True

        with self.assertRaises(OSError):
            extract_archive(
                input_file, self.output_folder, self.log_file, self.file_filter
            )

    @patch("subprocess.call")
    @patch("subprocess.check_output")
    @patch("shutil.which")
    def test_extract_archive_zip_ignore_prompts(
        self, mock_which, mock_check_output, mock_subprocess_call
    ):
        input_file = {"path": "/path/to/archive.zip", "display_name": "archive.zip"}
        mock_check_output.return_value = b""
        mock_which.return_value = True
        mock_subprocess_call.return_value = 0

        result = extract_archive(
            input_file,
            self.output_folder,
            self.log_file,
            self.file_filter,
            ignore_prompts=True,
        )
        self.assertIn("7z x", result[0])
        self.assertIn(" -y", result[0])
        self.assertIn(self.output_folder, result[1])

    @patch("subprocess.call")
    @patch("subprocess.check_output")
    @patch("shutil.which")
    def test_extract_archive_zip_no_ignore_prompts(
        self, mock_which, mock_check_output, mock_subprocess_call
    ):
        input_file = {"path": "/path/to/archive.zip", "display_name": "archive.zip"}
        mock_check_output.return_value = b""
        mock_which.return_value = True
        mock_subprocess_call.return_value = 0

        result = extract_archive(
            input_file,
            self.output_folder,
            self.log_file,
            self.file_filter,
            ignore_prompts=False,
        )
        self.assertIn("7z x", result[0])
        self.assertNotIn(" -y", result[0])
        self.assertIn(self.output_folder, result[1])

    @patch("subprocess.call")
    @patch("subprocess.check_output")
    @patch("shutil.which")
    def test_extract_archive_tgz_ignore_prompts_ignored(
        self, mock_which, mock_check_output, mock_subprocess_call
    ):
        input_file = {"path": "/path/to/archive.tgz", "display_name": "archive.tgz"}
        mock_check_output.return_value = b""
        mock_which.return_value = True
        mock_subprocess_call.return_value = 0

        result = extract_archive(
            input_file,
            self.output_folder,
            self.log_file,
            self.file_filter,
            ignore_prompts=True,
        )
        self.assertIn("tar -vxzf", result[0])
        self.assertNotIn(" -y", result[0])
        self.assertIn(self.output_folder, result[1])

    def test_malformed_input_file(self):
        input_file = {}

        with self.assertRaises(RuntimeError):
            extract_archive(
                input_file, self.output_folder, self.log_file, self.file_filter
            )

if __name__ == "__main__":
    unittest.main()
