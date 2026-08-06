from __future__ import annotations

import argparse
import json

from .runtime import build_controller_from_env


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Epsilon Research Controller v1"
        )
    )

    parser.add_argument(
        "question",
        help="Pregunta a investigar",
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="Imprime el resultado completo en JSON",
    )

    args = parser.parse_args()

    controller = build_controller_from_env()

    result = controller.run(
        args.question
    )

    if args.json:
        print(
            json.dumps(
                result.to_dict(),
                ensure_ascii=False,
                indent=2,
            )
        )

    else:
        print(result.answer)
        print()
        print("===== DIAGNÓSTICO =====")
        print(
            json.dumps(
                result.diagnostics,
                ensure_ascii=False,
                indent=2,
            )
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
