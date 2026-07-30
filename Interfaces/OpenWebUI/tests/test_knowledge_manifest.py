from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path
import unittest


INTERFACE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(INTERFACE_DIR))

from knowledge import KnowledgeManager, KnowledgeManagerError


class KnowledgeManifestTests(unittest.TestCase):
    """Pruebas locales del manifiesto y staging de Knowledge."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory(
            prefix="epsilon-knowledge-tests-"
        )
        self.project_root = Path(
            self.temporary_directory.name
        )

        self.interface_dir = (
            self.project_root
            / "Interfaces"
            / "OpenWebUI"
        )
        self.interface_dir.mkdir(
            parents=True
        )

        self.manifest_path = (
            self.interface_dir
            / "knowledge_manifest.txt"
        )
        self.manifest_path.write_text(
            "",
            encoding="utf-8",
        )

        (
            self.interface_dir
            / "knowledge_target.json"
        ).write_text(
            (
                "{\n"
                '  "source_name": "epsilon-system",\n'
                '  "model_id": "epsilon",\n'
                '  "slots": {\n'
                '    "blue": {"kb_id": "blue-test"},\n'
                '    "green": {"kb_id": "green-test"}\n'
                "  }\n"
                "}\n"
            ),
            encoding="utf-8",
        )

        (
            self.interface_dir
            / "oikb_bridge.py"
        ).write_text(
            "",
            encoding="utf-8",
        )

        python_executable = (
            self.interface_dir
            / ".venv"
            / "bin"
            / "python3"
        )
        python_executable.parent.mkdir(
            parents=True
        )
        python_executable.write_text(
            "",
            encoding="utf-8",
        )

        (self.project_root / "Core").mkdir()
        (self.project_root / "Knowledge").mkdir()

        subprocess.run(
            [
                "git",
                "init",
                "--quiet",
            ],
            cwd=self.project_root,
            check=True,
        )

        self.manager = KnowledgeManager(
            project_root=self.project_root,
            config=object(),
            client=object(),
            source_name="epsilon-system",
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def write_file(
        self,
        relative_path: str,
        content: str = "# Documento de prueba\n",
    ) -> Path:
        path = self.project_root / relative_path
        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        path.write_text(
            content,
            encoding="utf-8",
        )
        return path

    def write_manifest(
        self,
        *relative_paths: str,
    ) -> None:
        content = "\n".join(relative_paths)

        if relative_paths:
            content += "\n"

        self.manifest_path.write_text(
            content,
            encoding="utf-8",
        )

    def track(
        self,
        *relative_paths: str,
    ) -> None:
        subprocess.run(
            [
                "git",
                "add",
                "--",
                *relative_paths,
            ],
            cwd=self.project_root,
            check=True,
        )

    def test_accepts_valid_tracked_files(self) -> None:
        self.write_file("Core/EPSILON_CORE.md")
        self.write_file("Knowledge/Game/CURRENT_STATE.md")

        self.track(
            "Core/EPSILON_CORE.md",
            "Knowledge/Game/CURRENT_STATE.md",
        )

        self.write_manifest(
            "Core/EPSILON_CORE.md",
            "Knowledge/Game/CURRENT_STATE.md",
        )

        self.assertEqual(
            self.manager._manifest_paths(),
            (
                "Core/EPSILON_CORE.md",
                "Knowledge/Game/CURRENT_STATE.md",
            ),
        )

    def test_rejects_empty_manifest(self) -> None:
        self.manifest_path.write_text(
            "\n# Solo un comentario\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(
            KnowledgeManagerError,
            "manifiesto de Knowledge está vacío",
        ):
            self.manager._manifest_paths()

    def test_rejects_duplicate_paths(self) -> None:
        self.write_file("Core/EPSILON_CORE.md")
        self.track("Core/EPSILON_CORE.md")

        self.write_manifest(
            "Core/EPSILON_CORE.md",
            "Core/EPSILON_CORE.md",
        )

        with self.assertRaisesRegex(
            KnowledgeManagerError,
            "rutas duplicadas",
        ):
            self.manager._manifest_paths()

    def test_rejects_paths_outside_allowed_directories(
        self,
    ) -> None:
        self.write_file("Other/PRIVATE.md")
        self.write_manifest("Other/PRIVATE.md")

        with self.assertRaisesRegex(
            KnowledgeManagerError,
            "solo puede publicar archivos de Core/ o Knowledge/",
        ):
            self.manager._manifest_paths()

    def test_rejects_parent_directory_traversal(
        self,
    ) -> None:
        self.write_manifest(
            "Core/../Knowledge/PRIVATE.md"
        )

        with self.assertRaisesRegex(
            KnowledgeManagerError,
            "Ruta inválida",
        ):
            self.manager._manifest_paths()

    def test_rejects_missing_file(self) -> None:
        self.write_manifest(
            "Core/MISSING.md"
        )

        with self.assertRaisesRegex(
            KnowledgeManagerError,
            "no existe",
        ):
            self.manager._manifest_paths()

    def test_rejects_untracked_file(self) -> None:
        self.write_file(
            "Knowledge/UNTRACKED.md"
        )
        self.write_manifest(
            "Knowledge/UNTRACKED.md"
        )

        with self.assertRaisesRegex(
            KnowledgeManagerError,
            "no registrados por Git",
        ):
            self.manager._manifest_paths()

    def test_rejects_direct_symlink(self) -> None:
        target = self.write_file(
            "Core/EPSILON_CORE.md"
        )
        symlink = (
            self.project_root
            / "Knowledge"
            / "SYMLINK.md"
        )

        try:
            symlink.symlink_to(target)
        except OSError as error:
            self.skipTest(
                f"El sistema no permite symlinks: {error}"
            )

        self.write_manifest(
            "Knowledge/SYMLINK.md"
        )

        with self.assertRaisesRegex(
            KnowledgeManagerError,
            "enlaces simbólicos",
        ):
            self.manager._manifest_paths()

    def test_rejects_symlinked_parent_directory(
        self,
    ) -> None:
        target_directory = (
            self.project_root
            / "Core"
        )
        self.write_file(
            "Core/EPSILON_CORE.md"
        )

        symlink_directory = (
            self.project_root
            / "Knowledge"
            / "Alias"
        )

        try:
            symlink_directory.symlink_to(
                target_directory,
                target_is_directory=True,
            )
        except OSError as error:
            self.skipTest(
                f"El sistema no permite symlinks: {error}"
            )

        self.write_manifest(
            "Knowledge/Alias/EPSILON_CORE.md"
        )

        with self.assertRaisesRegex(
            KnowledgeManagerError,
            "enlaces simbólicos",
        ):
            self.manager._manifest_paths()

    def test_staging_is_exact_and_is_removed(self) -> None:
        core_content = "# Core exacto\n"
        state_content = "# Estado exacto\n"

        self.write_file(
            "Core/EPSILON_CORE.md",
            core_content,
        )
        self.write_file(
            "Knowledge/Game/CURRENT_STATE.md",
            state_content,
        )

        self.track(
            "Core/EPSILON_CORE.md",
            "Knowledge/Game/CURRENT_STATE.md",
        )

        self.write_manifest(
            "Core/EPSILON_CORE.md",
            "Knowledge/Game/CURRENT_STATE.md",
        )

        staging_path: Path | None = None

        with self.manager.staged_source() as staging:
            staging_path = staging

            staged_files = tuple(
                sorted(
                    path.relative_to(staging).as_posix()
                    for path in staging.rglob("*")
                    if path.is_file()
                )
            )

            self.assertEqual(
                staged_files,
                (
                    "Core/EPSILON_CORE.md",
                    "Knowledge/Game/CURRENT_STATE.md",
                ),
            )

            self.assertEqual(
                (
                    staging
                    / "Core"
                    / "EPSILON_CORE.md"
                ).read_text(encoding="utf-8"),
                core_content,
            )

            self.assertEqual(
                (
                    staging
                    / "Knowledge"
                    / "Game"
                    / "CURRENT_STATE.md"
                ).read_text(encoding="utf-8"),
                state_content,
            )

        self.assertIsNotNone(staging_path)
        self.assertFalse(staging_path.exists())


if __name__ == "__main__":
    unittest.main()