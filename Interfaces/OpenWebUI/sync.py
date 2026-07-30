from __future__ import annotations

import argparse
import json
import stat
import subprocess

from pathlib import Path
from shutil import which
from typing import Sequence

from client import (
    OpenWebUIAuthenticationError,
    OpenWebUIClient,
    OpenWebUIClientError,
)

from config import Config
from knowledge import KnowledgeManager, KnowledgeManagerError
from ollama_client import OllamaClient, OllamaClientError
from projection import ProjectionManager
from results import (
    DiagnosticResult,
    KnowledgeDiffResult,
    Plan,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
INTERFACE_DIR = Path(__file__).resolve().parent


def find_oikb() -> Path | None:
    """Busca oikb en el entorno virtual del proyecto o en PATH."""

    candidates = (
        INTERFACE_DIR / ".venv" / "bin" / "oikb",
        INTERFACE_DIR / ".venv" / "Scripts" / "oikb.exe",
    )

    for candidate in candidates:
        if candidate.is_file():
            return candidate

    executable = which("oikb")

    if executable:
        return Path(executable)

    return None


def check_file(component: str, path: Path) -> DiagnosticResult:
    if path.is_file():
        return DiagnosticResult(
            component=component,
            status="ok",
            summary=f"Presente: {path.relative_to(PROJECT_ROOT)}",
        )

    return DiagnosticResult(
        component=component,
        status="error",
        summary=f"No encontrado: {path.relative_to(PROJECT_ROOT)}",
    )


def check_directory(component: str, path: Path) -> DiagnosticResult:
    if path.is_dir():
        return DiagnosticResult(
            component=component,
            status="ok",
            summary=f"Presente: {path.relative_to(PROJECT_ROOT)}/",
        )

    return DiagnosticResult(
        component=component,
        status="error",
        summary=f"No encontrado: {path.relative_to(PROJECT_ROOT)}/",
    )


def collect_local_diagnostics() -> list[DiagnosticResult]:
    """Comprueba solamente el estado local; no escribe ni usa la red."""

    results = [
        check_directory("Project root", PROJECT_ROOT),
        check_directory("Core", PROJECT_ROOT / "Core"),
        check_directory("Knowledge", PROJECT_ROOT / "Knowledge"),
        check_directory("Skills", PROJECT_ROOT / "Skills"),
        check_file(
            "Projection",
            INTERFACE_DIR / "EPSILON_PROJECTION.md",
        ),
        check_file(
            "Knowledge manifest",
            INTERFACE_DIR / "knowledge_manifest.txt",
        ),
        check_file(
            "Knowledge target",
            INTERFACE_DIR / "knowledge_target.json",
        ),
    ]

    oikb_executable = find_oikb()

    if oikb_executable is None:
        results.append(
            DiagnosticResult(
                component="oikb",
                status="error",
                summary="No se encontró el ejecutable",
            )
        )
    else:
        try:
            version_result = subprocess.run(
                [str(oikb_executable), "--version"],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            results.append(
                DiagnosticResult(
                    component="oikb",
                    status="error",
                    summary=(
                        "El ejecutable existe, pero no pudo iniciarse"
                    ),
                    details=(str(error),),
                )
            )
        else:
            version_output = (
                version_result.stdout.strip()
                or version_result.stderr.strip()
            )

            if version_result.returncode != 0:
                results.append(
                    DiagnosticResult(
                        component="oikb",
                        status="error",
                        summary="El ejecutable devolvió un error",
                        details=(
                            version_output
                            or (
                                "Código de salida: "
                                f"{version_result.returncode}"
                            ),
                        ),
                    )
                )
            else:
                results.append(
                    DiagnosticResult(
                        component="oikb",
                        status="ok",
                        summary=(
                            version_output
                            or f"Ejecutable: {oikb_executable}"
                        ),
                    )
                )
        target_path = INTERFACE_DIR / "knowledge_target.json"

    if target_path.is_file():
        try:
            target_document = json.loads(
                target_path.read_text(encoding="utf-8")
            )
        except OSError as error:
            results.append(
                DiagnosticResult(
                    component="Knowledge target config",
                    status="error",
                    summary="No fue posible leer la configuración",
                    details=(str(error),),
                )
            )
        except json.JSONDecodeError as error:
            results.append(
                DiagnosticResult(
                    component="Knowledge target config",
                    status="error",
                    summary="El archivo no contiene JSON válido",
                    details=(str(error),),
                )
            )
        else:
            source_name = (
                target_document.get("source_name")
                if isinstance(target_document, dict)
                else None
            )
            kb_id = (
                target_document.get("kb_id")
                if isinstance(target_document, dict)
                else None
            )

            if (
                not isinstance(source_name, str)
                or not source_name.strip()
                or not isinstance(kb_id, str)
                or not kb_id.strip()
            ):
                results.append(
                    DiagnosticResult(
                        component="Knowledge target config",
                        status="error",
                        summary=(
                            "Debe contener source_name y kb_id válidos"
                        ),
                    )
                )
            else:
                results.append(
                    DiagnosticResult(
                        component="Knowledge target config",
                        status="ok",
                        summary=(
                            f"Destino válido: {source_name.strip()}"
                        ),
                        details=(f"KB: {kb_id.strip()}",),
                    )
                )

    ollama_executable = which("ollama")

    if ollama_executable:
        results.append(
            DiagnosticResult(
                component="Ollama CLI",
                status="ok",
                summary=f"Disponible: {ollama_executable}",
            )
        )
    else:
        results.append(
            DiagnosticResult(
                component="Ollama CLI",
                status="warning",
                summary="No se encontró en PATH",
            )
        )

    config = Config()

    results.append(
        DiagnosticResult(
            component="Ollama URL",
            status="ok",
            summary=config.ollama_url,
        )
    )

    ollama_client = OllamaClient(
        base_url=config.ollama_url,
        timeout_seconds=config.timeout_seconds,
    )

    try:
        ollama_version = ollama_client.version()
        installed_models = ollama_client.list_models()

    except OllamaClientError as error:
        results.append(
            DiagnosticResult(
                component="Ollama service",
                status="error",
                summary=str(error),
            )
        )

    else:
        results.append(
            DiagnosticResult(
                component="Ollama service",
                status="ok",
                summary="Servicio disponible",
            )
        )

        results.append(
            DiagnosticResult(
                component="Ollama version",
                status="ok",
                summary=ollama_version,
            )
        )

        expected_model = config.ollama_model

        model = next(
            (
                item
                for item in installed_models
                if item.get("name") == expected_model
                or item.get("model") == expected_model
            ),
            None,
        )

        if model is None:
            results.append(
                DiagnosticResult(
                    component="Ollama model",
                    status="error",
                    summary=f"No instalado: {expected_model}",
                )
            )

        else:
            results.append(
                DiagnosticResult(
                    component="Ollama model",
                    status="ok",
                    summary=f"Instalado: {expected_model}",
                )
            )

            digest = model.get("digest")

            if isinstance(digest, str) and digest:
                results.append(
                    DiagnosticResult(
                        component="Model digest",
                        status="ok",
                        summary=digest[:12],
                    )
                )
            else:
                results.append(
                    DiagnosticResult(
                        component="Model digest",
                        status="warning",
                        summary="No informado",
                    )
                )

            details = model.get("details")

            if not isinstance(details, dict):
                details = {}

            quantization = details.get("quantization_level")

            if isinstance(quantization, str) and quantization:
                results.append(
                    DiagnosticResult(
                        component="Quantization",
                        status="ok",
                        summary=quantization,
                    )
                )
            else:
                results.append(
                    DiagnosticResult(
                        component="Quantization",
                        status="warning",
                        summary="No informada",
                    )
                )

            parameter_size = details.get("parameter_size")

            if isinstance(parameter_size, str) and parameter_size:
                results.append(
                    DiagnosticResult(
                        component="Parameter size",
                        status="ok",
                        summary=parameter_size,
                    )
                )
                
    results.append(
        DiagnosticResult(
            component="Open WebUI URL",
            status="ok",
            summary=config.base_url,
        )
    )

    client = OpenWebUIClient(config)

    try:
        client.health()
    except OpenWebUIClientError as error:
        results.append(
            DiagnosticResult(
                component="Open WebUI health",
                status="error",
                summary=str(error),
            )
        )
    else:
        results.append(
            DiagnosticResult(
                component="Open WebUI health",
                status="ok",
                summary="Servicio disponible",
            )
        )

    credentials_path = config.credentials_path

    if credentials_path.is_file():
        try:
            file_mode = stat.S_IMODE(
                credentials_path.stat().st_mode
            )
            directory_mode = stat.S_IMODE(
                credentials_path.parent.stat().st_mode
            )
        except OSError as error:
            results.append(
                DiagnosticResult(
                    component="Credentials file",
                    status="error",
                    summary=f"No se pudieron revisar los permisos: {error}",
                )
            )
        else:
            if file_mode == 0o600 and directory_mode == 0o700:
                results.append(
                    DiagnosticResult(
                        component="Credentials file",
                        status="ok",
                        summary="Presente y protegido",
                    )
                )
            else:
                results.append(
                    DiagnosticResult(
                        component="Credentials file",
                        status="warning",
                        summary=(
                            "Permisos esperados: carpeta 700, "
                            "archivo 600"
                        ),
                        details=(
                            f"Carpeta actual: {directory_mode:o}",
                            f"Archivo actual: {file_mode:o}",
                        ),
                    )
                )
    else:
        results.append(
            DiagnosticResult(
                component="Credentials file",
                status="warning",
                summary=f"No encontrado: {credentials_path}",
            )
        )

    if not config.has_api_key:
        results.append(
            DiagnosticResult(
                component="Open WebUI API key",
                status="warning",
                summary="No está configurada",
            )
        )

    else:
        try:
            models = client.list_models()

        except OpenWebUIAuthenticationError as error:
            results.append(
                DiagnosticResult(
                    component="Open WebUI API key",
                    status="error",
                    summary=str(error),
                )
            )

        except OpenWebUIClientError as error:
            results.append(
                DiagnosticResult(
                    component="Open WebUI API",
                    status="error",
                    summary=str(error),
                )
            )

        else:
            results.append(
                DiagnosticResult(
                    component="Open WebUI API key",
                    status="ok",
                    summary="Aceptada por Open WebUI",
                )
            )

            results.append(
                DiagnosticResult(
                    component="Open WebUI models",
                    status="ok",
                    summary=f"{len(models)} modelos visibles",
                )
            )

            expected_model = config.openwebui_model
            model = client.find_model(
                expected_model,
                models=models,
            )

            if model is None:
                results.append(
                    DiagnosticResult(
                        component="Epsilon model",
                        status="error",
                        summary=f"No encontrado: {expected_model}",
                    )
                )
            else:
                results.append(
                    DiagnosticResult(
                        component="Epsilon model",
                        status="ok",
                        summary=f"Disponible: {expected_model}",
                    )
                )

    return results


def print_diagnostics(results: Sequence[DiagnosticResult]) -> None:
    symbols = {
        "ok": "✓",
        "warning": "!",
        "error": "✗",
    }

    print("===================================")
    print("       EPSILON DOCTOR")
    print("===================================\n")

    for result in results:
        symbol = symbols[result.status]
        print(f"{symbol} {result.component:<24} {result.summary}")

        for detail in result.details:
            print(f"    {detail}")

    errors = sum(result.status == "error" for result in results)
    warnings = sum(result.status == "warning" for result in results)

    print()
    print(f"Errores: {errors}")
    print(f"Advertencias: {warnings}")
    print("No se aplicaron cambios.")


def run_doctor() -> int:
    results = collect_local_diagnostics()
    print_diagnostics(results)

    return 1 if any(result.failed for result in results) else 0

def build_projection_manager(
    config: Config,
    client: OpenWebUIClient,
) -> ProjectionManager:
    """Construye el gestor de Projection."""

    return ProjectionManager(
        project_root=PROJECT_ROOT,
        client=client,
        model_id=config.openwebui_model,
        base_model_id=config.ollama_model,
    )


def build_knowledge_manager(
    config: Config,
    client: OpenWebUIClient,
) -> KnowledgeManager:
    """Construye el gestor de Knowledge."""

    return KnowledgeManager(
        project_root=PROJECT_ROOT,
        config=config,
        client=client,
        source_name="epsilon-system",
    )

def print_plan(
    plan: Plan,
    knowledge: KnowledgeDiffResult | None = None,
    *,
    footer: str | None = "No se aplicaron cambios.",
) -> None:
    """Muestra los cambios detectados sin ejecutarlos."""

    print("===================================")
    print("        EPSILON PLAN")
    print("===================================\n")

    if not plan.has_changes:
        print("✓ Projection             Sin cambios")
    else:
        symbols = {
            "create": "+",
            "update": "~",
        }

        for change in plan.changes:
            symbol = symbols[change.action]

            print(
                f"{symbol} {change.component:<22} "
                f"{change.summary}"
            )

            for reason in change.reasons:
                print(f"    - {reason}")

    if knowledge is not None:
        if not knowledge.has_changes:
            print(
                "✓ Knowledge              "
                f"Sin cambios ({knowledge.unmodified} archivos)"
            )
        else:
            print(
                "~ Knowledge              "
                "No coincide con los archivos autorizados"
            )
            print(f"    - Agregar archivos: {knowledge.added}")
            print(f"    - Modificar archivos: {knowledge.modified}")
            print(f"    - Eliminar archivos: {knowledge.deleted}")
            print(
                "    - Crear carpetas: "
                f"{knowledge.dirs_created}"
            )
            print(
                "    - Retirar carpetas: "
                f"{knowledge.dirs_removed}"
            )

            if knowledge.has_destructive_changes:
                print(
                    "    ! Contiene operaciones "
                    "potencialmente destructivas."
                )

        for warning in knowledge.warnings:
            print(f"    ! {warning}")

    print()
    print("Resumen de Projection:")
    print(f"  Crear:      {plan.create_count}")
    print(f"  Actualizar: {plan.update_count}")
    print(f"  Total:      {len(plan.changes)}")

    if knowledge is not None:
        print()
        print("Resumen de Knowledge:")
        print(f"  Agregar:          {knowledge.added}")
        print(f"  Modificar:        {knowledge.modified}")
        print(f"  Eliminar:         {knowledge.deleted}")
        print(f"  Carpetas crear:   {knowledge.dirs_created}")
        print(f"  Carpetas retirar: {knowledge.dirs_removed}")
        print(f"  Total:            {knowledge.total_changes}")

    if footer is not None:
        print()
        print(footer)


def run_plan() -> int:
    """Compara el repositorio con el estado activo sin escribir."""

    try:
        config = Config()

        with OpenWebUIClient(config) as client:
            projection_manager = build_projection_manager(
                config,
                client,
            )
            knowledge_manager = build_knowledge_manager(
                config,
                client,
            )

            projection_plan = projection_manager.plan()
            knowledge_result = knowledge_manager.plan()

    except (
        FileNotFoundError,
        OSError,
        RuntimeError,
        KnowledgeManagerError,
        OpenWebUIClientError,
    ) as error:
        print("===================================")
        print("        EPSILON PLAN")
        print("===================================\n")
        print(f"✗ No fue posible construir el plan: {error}")
        print()
        print("No se aplicaron cambios.")
        return 1

    print_plan(
        projection_plan,
        knowledge_result,
    )

    return 0

def run_apply(confirmed: bool) -> int:
    """Aplica y verifica Projection con autorización explícita."""

    try:
        config = Config()

        with OpenWebUIClient(config) as client:
            manager = build_projection_manager(
                config,
                client,
            )

            plan = manager.plan()

            print_plan(
                plan,
                footer=None,
            )

            if not plan.has_changes:
                print()
                print(
                    "✓ No había cambios de Projection "
                    "que aplicar."
                )
                print(
                    "Knowledge todavía no se aplica "
                    "automáticamente."
                )
                return 0

            if not confirmed:
                print()
                print("✗ Aplicación no autorizada.")
                print(
                    "  Revisa el plan y repite el comando "
                    "con --yes para aprobarlo."
                )
                print("No se aplicaron cambios.")
                return 2

            try:
                manager.apply(plan)

            except (
                FileNotFoundError,
                OSError,
                RuntimeError,
                ValueError,
                OpenWebUIClientError,
            ) as error:
                print()
                print(f"✗ La aplicación falló: {error}")
                print(
                    "El resultado no fue considerado válido. "
                    "Revisa nuevamente doctor y plan."
                )
                return 1

    except (
        FileNotFoundError,
        OSError,
        RuntimeError,
        OpenWebUIClientError,
    ) as error:
        print("===================================")
        print("        EPSILON APPLY")
        print("===================================\n")
        print(f"✗ No fue posible construir el plan: {error}")
        print()
        print("No se aplicaron cambios.")
        return 1

    print()
    print("✓ Projection aplicada y verificada.")
    print(
        "Knowledge todavía no se aplica "
        "automáticamente."
    )

    return 0

def print_verification(
    plan: Plan,
    knowledge: KnowledgeDiffResult,
) -> None:
    """Muestra si Projection y Knowledge coinciden."""

    print("===================================")
    print("       EPSILON VERIFY")
    print("===================================\n")

    projection_verified = not plan.has_changes
    knowledge_verified = (
        not knowledge.failed
        and not knowledge.has_changes
    )

    if projection_verified:
        print("✓ Projection             Estado verificado")
    else:
        print("✗ Projection             No coincide con Git")

        symbols = {
            "create": "+",
            "update": "~",
        }

        for change in plan.changes:
            symbol = symbols[change.action]
            print(f"    {symbol} {change.summary}")

            for reason in change.reasons:
                print(f"      - {reason}")

    if knowledge_verified:
        print(
            "✓ Knowledge              "
            f"Estado verificado ({knowledge.unmodified} archivos)"
        )
    else:
        print(
            "✗ Knowledge              "
            "No coincide con los archivos autorizados"
        )
        print(f"    - Agregar archivos: {knowledge.added}")
        print(f"    - Modificar archivos: {knowledge.modified}")
        print(f"    - Eliminar archivos: {knowledge.deleted}")
        print(
            "    - Crear carpetas: "
            f"{knowledge.dirs_created}"
        )
        print(
            "    - Retirar carpetas: "
            f"{knowledge.dirs_removed}"
        )

        if knowledge.has_destructive_changes:
            print(
                "    ! Contiene operaciones "
                "potencialmente destructivas."
            )

    for warning in knowledge.warnings:
        print(f"    ! {warning}")

    print()

    if projection_verified and knowledge_verified:
        print(
            "El estado activo de Projection y Knowledge "
            "coincide con el repositorio."
        )
    else:
        print(
            "El estado activo no coincide completamente "
            "con el repositorio."
        )

    print("No se aplicaron cambios.")

def run_verify() -> int:
    """Verifica Projection y Knowledge sin modificar recursos."""

    try:
        config = Config()

        with OpenWebUIClient(config) as client:
            projection_manager = build_projection_manager(
                config,
                client,
            )
            knowledge_manager = build_knowledge_manager(
                config,
                client,
            )

            projection_plan = projection_manager.plan()
            knowledge_result = knowledge_manager.plan()

    except (
        FileNotFoundError,
        OSError,
        RuntimeError,
        KnowledgeManagerError,
        OpenWebUIClientError,
    ) as error:
        print("===================================")
        print("       EPSILON VERIFY")
        print("===================================\n")
        print(f"✗ No fue posible verificar el estado: {error}")
        print()
        print("No se aplicaron cambios.")
        return 1

    print_verification(
        projection_plan,
        knowledge_result,
    )

    if (
        projection_plan.has_changes
        or knowledge_result.failed
        or knowledge_result.has_changes
    ):
        return 1

    return 0

def build_parser() -> argparse.ArgumentParser:
    """Construye la interfaz de comandos de Epsilon."""

    parser = argparse.ArgumentParser(
        description="Diagnóstico y reconciliación de Epsilon.",
    )

    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser(
        "doctor",
        help="Comprueba dependencias y configuración.",
    )

    subparsers.add_parser(
        "plan",
        help="Compara el estado deseado y el estado activo.",
    )

    apply_parser = subparsers.add_parser(
        "apply",
        help="Aplica explícitamente un plan aprobado.",
    )

    apply_parser.add_argument(
        "--yes",
        action="store_true",
        help="Autoriza explícitamente la escritura en Open WebUI.",
    )

    subparsers.add_parser(
        "verify",
        help="Verifica el estado activo sin aplicar cambios.",
    )

    return parser

def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    arguments = parser.parse_args(argv)

    if arguments.command is None:
        parser.print_help()
        return 0

    if arguments.command == "doctor":
        return run_doctor()

    if arguments.command == "plan":
        return run_plan()

    if arguments.command == "apply":
        return run_apply(arguments.yes)

    if arguments.command == "verify":
        return run_verify()

    parser.error(
        f"Comando no reconocido: {arguments.command}"
    )
    return 2

if __name__ == "__main__":
    raise SystemExit(main())
