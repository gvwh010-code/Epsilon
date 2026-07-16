from pathlib import Path

from client import OpenWebUIClient

from projection import ProjectionManager
from knowledge import KnowledgeManager
from skills import SkillsManager


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    print("===================================")
    print("      EPSILON OPENWEBUI SYNC")
    print("===================================\n")

    client = OpenWebUIClient()

    modules = [
        ProjectionManager(PROJECT_ROOT, client),
        KnowledgeManager(PROJECT_ROOT),
        SkillsManager(PROJECT_ROOT, client),
    ]

    success = True

    for module in modules:
        print(f"{module.name}:\n")

        result = module.sync(dry_run=False)

        if not result:
            success = False

        print()

    if success:
        print("✓ Sincronización completada")
    else:
        print("✗ Sincronización finalizada con errores")


if __name__ == "__main__":
    main()