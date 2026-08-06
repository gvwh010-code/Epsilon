from __future__ import annotations

import json
import os
from http.server import (
    BaseHTTPRequestHandler,
    HTTPServer,
)
from typing import Any

from Tools.Research.runtime import (
    build_controller_from_env,
)


MAX_REQUEST_BYTES = 64 * 1024


class ResearchHTTPServer(HTTPServer):
    def __init__(
        self,
        server_address,
        handler_class,
    ):
        super().__init__(
            server_address,
            handler_class,
        )

        self.controller = (
            build_controller_from_env()
        )


class ResearchHandler(BaseHTTPRequestHandler):
    server: ResearchHTTPServer

    def _send_json(
        self,
        status: int,
        payload: dict[str, Any],
    ) -> None:
        body = json.dumps(
            payload,
            ensure_ascii=False,
        ).encode("utf-8")

        self.send_response(status)
        self.send_header(
            "Content-Type",
            "application/json; charset=utf-8",
        )
        self.send_header(
            "Content-Length",
            str(len(body)),
        )
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send_json(
                200,
                {
                    "status": "ok",
                    "service": "epsilon-research",
                    "version": "1",
                },
            )
            return

        self._send_json(
            404,
            {
                "error": "not_found",
            },
        )

    def do_POST(self) -> None:
        if self.path != "/v1/research":
            self._send_json(
                404,
                {
                    "error": "not_found",
                },
            )
            return

        content_length = self.headers.get(
            "Content-Length"
        )

        try:
            length = int(content_length or "0")
        except ValueError:
            self._send_json(
                400,
                {
                    "error": "invalid_content_length",
                },
            )
            return

        if (
            length <= 0
            or length > MAX_REQUEST_BYTES
        ):
            self._send_json(
                413,
                {
                    "error": "invalid_request_size",
                },
            )
            return

        try:
            raw = self.rfile.read(length)
            payload = json.loads(
                raw.decode("utf-8")
            )
        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
        ):
            self._send_json(
                400,
                {
                    "error": "invalid_json",
                },
            )
            return

        if not isinstance(payload, dict):
            self._send_json(
                400,
                {
                    "error": "invalid_request",
                },
            )
            return

        question = payload.get("question")

        if (
            not isinstance(question, str)
            or not question.strip()
        ):
            self._send_json(
                400,
                {
                    "error": "invalid_question",
                },
            )
            return

        try:
            result = self.server.controller.run(
                question
            )
        except Exception as error:
            self._send_json(
                500,
                {
                    "error": "research_failed",
                    "detail": str(error),
                },
            )
            return

        self._send_json(
            200,
            result.to_dict(),
        )

    def log_message(
        self,
        format: str,
        *args: Any,
    ) -> None:
        print(
            "[epsilon-research] "
            + format % args
        )


def main() -> int:
    host = os.environ.get(
        "RESEARCH_SERVICE_HOST",
        "127.0.0.1",
    )

    port = int(
        os.environ.get(
            "RESEARCH_SERVICE_PORT",
            "10002",
        )
    )

    server = ResearchHTTPServer(
        (host, port),
        ResearchHandler,
    )

    print(
        "Epsilon Research Service v1"
    )
    print(
        f"Listening on http://{host}:{port}"
    )

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
        print("Research service detenido.")
    finally:
        server.server_close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
