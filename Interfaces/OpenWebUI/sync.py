from pathlib import Path

from client import OpenWebUIClient


PROJECT_ROOT = Path(__file__).resolve().parents[2]

PROJECTION_PATH = (
    PROJECT_ROOT
    / "Interfaces"
    / "OpenWebUI"
    / "EPSILON_PROJECTION.md"
)


def normalize_text(text: str) -> str:
    return text.replace("\r\n", "\n").strip()


def main() -> None:
    print("===================================")
    print("      EPSILON OPENWEBUI SYNC")
    print("===================================\n")

    client = OpenWebUIClient()

    try:
        model = client.get("/api/v1/models/model?id=epsilon")
        remote_prompt = model.get("params", {}).get("system", "")

        local_prompt = PROJECTION_PATH.read_text(encoding="utf-8")

        local_normalized = normalize_text(local_prompt)
        remote_normalized = normalize_text(remote_prompt)

        print("✓ Modelo Epsilon leído correctamente")
        print(f"✓ Proyección local encontrada: {PROJECTION_PATH}\n")

        if local_normalized == remote_normalized:
            print("✓ System Prompt sincronizado")
        else:
            print("✗ System Prompt diferente")
            print("\nRepositorio:")
            print(f"  {len(local_normalized)} caracteres")
            print("\nOpen WebUI:")
            print(f"  {len(remote_normalized)} caracteres")

    except FileNotFoundError:
        print("✗ No se encontró EPSILON_PROJECTION.md")
        print(PROJECTION_PATH)

    except Exception as error:
        print("✗ Error durante la comparación")
        print(error)


if __name__ == "__main__":
    main()