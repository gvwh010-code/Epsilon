from __future__ import annotations

from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest


INTERFACE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(INTERFACE_DIR))

from knowledge import (
    KnowledgeManager,
    KnowledgeManagerError,
)


class LockOnlyKnowledgeManager(KnowledgeManager):
    """Manager mínimo para probar únicamente flock."""

    def __init__(
        self,
        project_root: Path,
    ) -> None:
        self.project_root = project_root


class KnowledgeDeploymentLockTests(unittest.TestCase):
    """Pruebas del bloqueo exclusivo de despliegue."""

    def test_rejects_second_operation_for_same_project(
        self,
    ) -> None:
        with TemporaryDirectory() as directory:
            project_root = Path(directory)

            first = LockOnlyKnowledgeManager(
                project_root
            )
            second = LockOnlyKnowledgeManager(
                project_root
            )

            with first.deployment_lock():
                with self.assertRaisesRegex(
                    KnowledgeManagerError,
                    "otra operación de despliegue",
                ):
                    with second.deployment_lock():
                        self.fail(
                            "El segundo proceso adquirió "
                            "un bloqueo ya ocupado."
                        )

    def test_releases_lock_after_context(
        self,
    ) -> None:
        with TemporaryDirectory() as directory:
            project_root = Path(directory)

            first = LockOnlyKnowledgeManager(
                project_root
            )
            second = LockOnlyKnowledgeManager(
                project_root
            )

            with first.deployment_lock():
                pass

            with second.deployment_lock():
                pass


if __name__ == "__main__":
    unittest.main()
