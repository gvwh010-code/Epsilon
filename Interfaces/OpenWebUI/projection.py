from pathlib import Path
from typing import Any

from sync_module import SyncModule


class ProjectionManager(SyncModule):
    name = "Projection"

    def __init__(self, project_root: Path, client):
        self.project_root = project_root
        self.client = client
        self.projection_path = (
            project_root
            / "Interfaces"
            / "OpenWebUI"
            / "EPSILON_PROJECTION.md"
        )

    @staticmethod
    def normalize_text(text: str) -> str:
        return text.replace("\r\n", "\n").strip()

    def read_local(self) -> str:
        return self.projection_path.read_text(encoding="utf-8")

    def read_remote(self) -> tuple[dict[str, Any], str]:
        model = self.client.get("/api/v1/models/model?id=epsilon")
        remote_prompt = model.get("params", {}).get("system", "")
        return model, remote_prompt

    def sync(self, dry_run: bool = True) -> bool:
        try:
            local_prompt = self.normalize_text(self.read_local())
            _, remote_prompt = self.read_remote()
            remote_prompt = self.normalize_text(remote_prompt)

            if local_prompt == remote_prompt:
                print("✓ Projection sincronizada")
                return True

            print("✗ Projection diferente")
            print(f"  Local:  {len(local_prompt)} caracteres")
            print(f"  Remota: {len(remote_prompt)} caracteres")

            if dry_run:
                print("  Dry-run: no se aplicaron cambios")
                return True

            print("  La actualización remota todavía no está implementada")
            return False

        except FileNotFoundError:
            print(f"✗ No se encontró: {self.projection_path}")
            return False

        except Exception as error:
            print(f"✗ Error en Projection: {error}")
            return False