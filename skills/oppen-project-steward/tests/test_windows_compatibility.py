from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "oppen_project_steward.py"
SPEC = importlib.util.spec_from_file_location(
    "oppen_project_steward_windows", SCRIPT_PATH
)
assert SPEC and SPEC.loader
steward = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = steward
SPEC.loader.exec_module(steward)


class WindowsCompatibilityTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.temp_root = Path(self.temporary.name).resolve()
        self.root = self.temp_root / "project"
        steward.initialize_new_project(self.root)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def memory_payload(self) -> Path:
        path = self.temp_root / "memory.json"
        path.write_text(
            json.dumps(
                {
                    "title": "Preserve Windows transaction continuity",
                    "related_topics": [],
                    "supersedes": [],
                    "invalidates": [],
                    "before": "Text writes relied on platform newline defaults.",
                    "trigger": "Windows translated generated LF bytes to CRLF.",
                    "decision": "Write deterministic managed text with explicit LF.",
                    "why": "The baseline hash must match the bytes promoted to disk.",
                    "rejected_or_prior_approach": "Platform-default translation was rejected.",
                    "consequence": "Managed text remains byte-identical across platforms.",
                }
            ),
            encoding="utf-8",
        )
        return path

    def test_atomic_and_transaction_text_staging_disable_newline_translation(
        self,
    ) -> None:
        original = tempfile.NamedTemporaryFile
        calls: list[dict[str, object]] = []

        def record(*args, **kwargs):
            calls.append(dict(kwargs))
            return original(*args, **kwargs)

        standalone = self.temp_root / "standalone.txt"
        with mock.patch.object(
            steward.tempfile, "NamedTemporaryFile", side_effect=record
        ):
            steward.atomic_write(standalone, "one\ntwo\n")
            steward.add_memory(self.root, self.memory_payload())

        text_calls = [call for call in calls if call.get("mode") == "w"]
        self.assertGreaterEqual(len(text_calls), 4)
        self.assertTrue(all(call.get("newline") == "\n" for call in text_calls))
        self.assertEqual(standalone.read_bytes(), b"one\ntwo\n")
        self.assertEqual(steward.validate_project(self.root).status, "MANAGED_READY")

    def test_windows_lock_backend_locks_one_initialized_byte(self) -> None:
        backend = mock.Mock()
        backend.LK_LOCK = 1
        backend.LK_UNLCK = 2

        with (
            mock.patch.object(steward, "fcntl", None),
            mock.patch.object(steward, "msvcrt", backend),
            steward.project_write_lock(self.root),
        ):
            pass

        self.assertEqual(
            [call.args[1:] for call in backend.locking.call_args_list],
            [(backend.LK_LOCK, 1), (backend.LK_UNLCK, 1)],
        )

    def test_missing_lock_backend_fails_instead_of_running_unlocked(self) -> None:
        with (
            mock.patch.object(steward, "fcntl", None),
            mock.patch.object(steward, "msvcrt", None),
            self.assertRaisesRegex(steward.ProjectError, "file-lock backend"),
        ):
            with steward.project_write_lock(self.root):
                pass

    def test_windows_temporary_roots_exclude_posix_conventions(self) -> None:
        with (
            mock.patch.object(steward, "IS_WINDOWS", True),
            mock.patch.object(
                steward.tempfile, "gettempdir", return_value=str(self.temp_root)
            ),
        ):
            roots = steward.system_temporary_roots()

        self.assertEqual(roots, (self.temp_root,))

    def test_audit_stage_rejects_windows_reserved_or_ambiguous_names(self) -> None:
        for stage in ("con", "nul.txt", "lpt1", "build."):
            with self.subTest(stage=stage):
                with self.assertRaises(steward.ProjectError):
                    steward.validate_portable_path_key(stage, "audit stage")
        self.assertEqual(
            steward.validate_portable_path_key("build-01", "audit stage"),
            "build-01",
        )

    def test_path_identity_uses_platform_case_normalization(self) -> None:
        with mock.patch.object(
            steward.os.path, "normcase", return_value="normalized-project"
        ) as normcase:
            identity = steward.normalized_path_identity(self.root)

        self.assertEqual(identity, "normalized-project")
        normcase.assert_called_once_with(os.path.normpath(str(self.root.resolve())))

    def test_existing_crlf_baseline_can_continue_without_reinitialization(self) -> None:
        namespace = self.root / steward.STEWARD_NAMESPACE
        baseline_path = namespace / steward.MANAGED_STATE_NAME
        generation = steward.load_managed_state(self.root).generation
        for relative in steward.load_managed_state(self.root).files:
            path = namespace / Path(relative)
            content = path.read_bytes().replace(b"\r\n", b"\n")
            path.write_bytes(content.replace(b"\n", b"\r\n"))
        baseline_path.write_text(
            steward.render_managed_state_for_namespace(namespace, generation),
            encoding="utf-8",
            newline="\n",
        )
        self.assertEqual(steward.validate_project(self.root).status, "MANAGED_READY")

        steward.add_memory(self.root, self.memory_payload())

        self.assertEqual(steward.validate_project(self.root).status, "MANAGED_READY")
        self.assertEqual(
            steward.managed_state_drift(
                self.root, steward.load_managed_state(self.root)
            ),
            (),
        )


if __name__ == "__main__":
    unittest.main()
