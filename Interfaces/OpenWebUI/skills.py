from pathlib import Path
from typing import Any

from sync_module import SyncModule


class SkillsManager(SyncModule):
    name = "Skills"

    def __init__(self, project_root: Path, client):
        self.project_root = project_root
        self.client = client
        self.skills_directory = project_root / "Skills"

    @staticmethod
    def parse_frontmatter(
        text: str,
    ) -> tuple[dict[str, str], str]:
        """Extrae name/description de un frontmatter YAML simple."""

        normalized = text.replace("\r\n", "\n")

        if not normalized.startswith("---\n"):
            return {}, normalized.strip()

        lines = normalized.splitlines()

        try:
            closing_index = lines.index("---", 1)
        except ValueError:
            return {}, normalized.strip()

        metadata: dict[str, str] = {}

        for line in lines[1:closing_index]:
            if ":" not in line:
                continue

            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()

            if key not in {"name", "description"}:
                continue

            if (
                len(value) >= 2
                and value[0] == value[-1]
                and value[0] in {'"', "'"}
            ):
                value = value[1:-1]

            metadata[key] = value

        content = "\n".join(
            lines[closing_index + 1:]
        ).strip()

        return metadata, content

    def read_local_skills(self) -> list[dict[str, Any]]:
        skills: list[dict[str, Any]] = []

        if not self.skills_directory.exists():
            return skills

        for path in sorted(self.skills_directory.glob("*.md")):
            raw_content = path.read_text(
                encoding="utf-8"
            )

            metadata, content = self.parse_frontmatter(
                raw_content
            )

            if not content:
                continue

            skill_id = path.stem.lower()

            default_name = (
                path.stem
                .replace("_", " ")
                .title()
            )

            skill_name = (
                metadata.get("name")
                or default_name
            )

            description = metadata.get(
                "description",
                "",
            )

            skills.append(
                {
                    "id": skill_id,
                    "name": skill_name,
                    "description": description,
                    "content": content,
                    "path": path,
                }
            )

        return skills

    def read_remote_skills(self) -> list[dict[str, Any]]:
        """Obtiene las Skills exportables con su contenido completo."""

        response = self.client.get("/api/v1/skills/export")

        if not isinstance(response, list):
            return []

        return [
            skill
            for skill in response
            if isinstance(skill, dict)
        ]

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
                    "description": local_skill["description"],
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

            local_content = self.normalize_text(
                local_skill["content"]
            )
            remote_content = self.normalize_text(
                remote_skill.get("content", "")
            )

            local_name = local_skill["name"]
            remote_name = remote_skill.get("name", "")

            local_description = local_skill["description"]
            remote_description = remote_skill.get(
                "description",
                "",
            )

            skill_matches = (
                local_content == remote_content
                and local_name == remote_name
                and local_description == remote_description
            )

            if skill_matches:
                print(
                    f"✓ {local_skill['name']} sincronizada"
                )

            else:
                print(f"~ Diferente: {local_skill['name']} ({skill_id})")

                if dry_run:
                    print("  Dry-run: no se aplicaron cambios")
                    success = False
                    continue

                payload = {
                    "id": remote_skill.get("id", skill_id),
                    "name": local_skill["name"],
                    "description": local_skill["description"],
                    "content": local_skill["content"],
                    "meta": remote_skill.get("meta", {"tags": []}),
                    "is_active": remote_skill.get("is_active", True),
                    "access_grants": remote_skill.get("access_grants", []),
                }

                self.client.post(
                    f"/api/v1/skills/id/{skill_id}/update",
                    payload,
                )

                print(f"✓ {local_skill['name']} actualizada")

        if dry_run and not success:
            print("Dry-run: no se aplicaron cambios")

        return success