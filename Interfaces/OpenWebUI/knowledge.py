from pathlib import Path
import subprocess

from sync_module import SyncModule


class KnowledgeManager(SyncModule):
    name = "Knowledge"

    def __init__(self, project_root: Path):
        self.project_root = project_root

        venv_dir = (
            project_root
            / "Interfaces"
            / "OpenWebUI"
            / ".venv"
        )

        windows_executable = venv_dir / "Scripts" / "oikb.exe"
        linux_executable = venv_dir / "bin" / "oikb"

        if windows_executable.exists():
            self.oikb_executable = windows_executable
        elif linux_executable.exists():
            self.oikb_executable = linux_executable
        else:
            raise FileNotFoundError(
                "No se encontró oikb dentro del entorno virtual. "
                "Instálalo con: pip install oikb"
            )

    def build_projection(self) -> None:
        import shutil

        projection_dir = (
            self.project_root
            / "Interfaces"
            / "OpenWebUI"
            / "knowledge_projection"
        )

        core_dir = self.project_root / "Core"
        knowledge_dir = self.project_root / "Knowledge"

        # Reconstruir completamente la proyección
        if projection_dir.exists():
            shutil.rmtree(projection_dir)

        projection_dir.mkdir(parents=True)

        print("Construyendo Knowledge Projection...")

        # Copiar todo Core
        if core_dir.exists():
            shutil.copytree(
                core_dir,
                projection_dir / "Core",
                dirs_exist_ok=True,
            )

        # Copiar todo Knowledge
        if knowledge_dir.exists():
            shutil.copytree(
                knowledge_dir,
                projection_dir / "Knowledge",
                dirs_exist_ok=True,
            )


    def validate(self) -> bool:
        return self._run(["validate"])

    def status(self) -> bool:
        return self._run(["status"])

    def sync(self, dry_run: bool = True) -> bool:

        self.build_projection()
        
        command = ["sync"]

        if dry_run:
            command.append("--dry-run")

        return self._run(command)

    def _run(self, arguments: list[str]) -> bool:
        import os

        environment = os.environ.copy()
        environment["PYTHONIOENCODING"] = "utf-8"
        environment["PYTHONUTF8"] = "1"

        result = subprocess.run(
            [str(self.oikb_executable), *arguments],
            cwd=self.project_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=environment,
            check=False,
        )

        if result.stdout:
            print(result.stdout.strip())

        if result.stderr:
            print(result.stderr.strip())

        return result.returncode == 0