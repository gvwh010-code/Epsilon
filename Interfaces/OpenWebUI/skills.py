from pathlib import Path
from typing import Any

from sync_module import SyncModule


class SkillsManager(SyncModule):
    name = "Skills"

    def __init__(self, project_root: Path, client):
        self.project_root = project_root
        self.client = client
        self.skills_directory = project_root / "Skills"

    def read_local_skills(self) -> list[dict[str, Any]]:
        skills: list[dict[str, Any]] = []

        if not self.skills_directory.exists():
            return skills

        for path in sorted(self.skills_directory.glob("*.md")):
            content = path.read_text(encoding="utf-8").strip()

            if not content:
                continue

            skill_id = path.stem.lower()
            skill_name = path.stem.replace("_", " ").title()

            skills.append(
                {
                    "id": skill_id,
                    "name": skill_name,
                    "content": content,
                    "path": path,
                }
            )

        return skills

    def read_remote_skills(self) -> list[dict[str, Any]]:
        response = self.client.get("/api/v1/skills/")

        if isinstance(response, dict):
            summaries = response.get("data", [])
        elif isinstance(response, list):
            summaries = response
        else:
            return []

        skills: list[dict[str, Any]] = []

        for summary in summaries:
            skill_id = summary.get("id")

            if not skill_id:
                continue

            skill = self.client.get(
                f"/api/v1/skills/id/{skill_id}"
            )

            skills.append(skill)

        return skills

    @staticmethod
    def normalize_text(text: str) -> str:
        return text.replace("\r\n", "\n").strip()

    def sync(self, dry_run: bool = True) -> bool:
        local_skills = self.read_local_skills()
        remote_skills = self.read_remote_skills()

        remote_by_id = {
            skill.get("id"): skill
            for skill in remote_skills
            if skill.get("id")
        }

        if not local_skills:
            print("No se encontraron Skills locales.")
            return True

        success = True

        for local_skill in local_skills:
            skill_id = local_skill["id"]
            remote_skill = remote_by_id.get(skill_id)

            if remote_skill is None:
                print(f"+ Falta crear: {local_skill['name']} ({skill_id})")

                if dry_run:
                    print("  Dry-run: no se aplicaron cambios")
                    success = False
                    continue

                payload = {
                    "id": skill_id,
                    "name": local_skill["name"],
                    "description": "",
                    "content": local_skill["content"],
                    "meta": {
                        "tags": []
                    },
                    "access_grants": [],
                }

                self.client.post(
                    "/api/v1/skills/create",
                    payload,
                )

                print(f"✓ {local_skill['name']} creada")
                continue

            local_content = self.normalize_text(local_skill["content"])
            remote_content = self.normalize_text(
                remote_skill.get("content", "")
            )

            if local_content == remote_content:
                print(f"✓ {local_skill['name']} sincronizada")

            else:
                print(f"~ Diferente: {local_skill['name']} ({skill_id})")

                if dry_run:
                    print("  Dry-run: no se aplicaron cambios")
                    success = False
                    continue

                payload = {
                    "id": remote_skill.get("id", skill_id),
                    "name": remote_skill.get("name", local_skill["name"]),
                    "description": remote_skill.get("description", ""),
                    "content": local_skill["content"],
                    "meta": remote_skill.get("meta", {"tags": []}),
                    "access_grants": remote_skill.get("access_grants", []),
                }

                self.client.post(
                    f"/api/v1/skills/id/{skill_id}/update",
                    payload,
                )

                print(f"✓ {local_skill['name']} actualizada")

        if dry_run and not success:
            print("Dry-run: no se aplicaron cambios")

        return True if dry_run else success