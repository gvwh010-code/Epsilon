from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys
import unittest
from typing import Any


INTERFACE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(INTERFACE_DIR))

from client import (
    OpenWebUIClient,
    OpenWebUIClientError,
)


class RecordingOpenWebUIClient(OpenWebUIClient):
    """Cliente local sin sesión HTTP."""

    def __init__(
        self,
        *,
        exported: list[dict[str, Any]] | None = None,
        response: Any = None,
    ) -> None:
        self.exported = deepcopy(exported or [])
        self.response = deepcopy(response)
        self.posts: list[
            tuple[str, dict[str, Any]]
        ] = []

    def export_models(self) -> list[dict[str, Any]]:
        return deepcopy(self.exported)

    def post(
        self,
        endpoint: str,
        payload: dict[str, Any],
    ) -> Any:
        self.posts.append(
            (
                endpoint,
                deepcopy(payload),
            )
        )
        return deepcopy(self.response)


class OpenWebUIClientModelTests(unittest.TestCase):
    """Pruebas de exportación y actualización individual."""

    def build_model(
        self,
        **overrides: Any,
    ) -> dict[str, Any]:
        model: dict[str, Any] = {
            "id": "epsilon",
            "base_model_id": "gemma4:12b",
            "name": "Epsilon",
            "meta": {
                "knowledge": [
                    {
                        "id": "blue-id",
                        "name": "Epsilon System",
                    }
                ],
                "skillIds": ["skill-id"],
            },
            "params": {
                "system": "controlled prompt",
            },
            "access_grants": [],
            "is_active": True,
            "created_at": 1,
            "updated_at": 2,
            "user_id": "owner-id",
        }
        model.update(overrides)
        return model

    def test_exports_exact_model_as_deep_copy(
        self,
    ) -> None:
        original = self.build_model()
        client = RecordingOpenWebUIClient(
            exported=[original]
        )

        exported = client.export_model("epsilon")

        self.assertEqual(exported, original)
        self.assertIsNot(exported, original)

        exported["meta"]["knowledge"].clear()

        self.assertEqual(
            len(client.exported[0]["meta"]["knowledge"]),
            1,
        )

    def test_rejects_blank_export_model_id(
        self,
    ) -> None:
        client = RecordingOpenWebUIClient()

        with self.assertRaisesRegex(
            ValueError,
            "identificador",
        ):
            client.export_model("   ")

    def test_rejects_missing_exported_model(
        self,
    ) -> None:
        client = RecordingOpenWebUIClient(
            exported=[]
        )

        with self.assertRaisesRegex(
            OpenWebUIClientError,
            "No existe",
        ):
            client.export_model("epsilon")

    def test_rejects_duplicate_exported_model(
        self,
    ) -> None:
        client = RecordingOpenWebUIClient(
            exported=[
                self.build_model(),
                self.build_model(),
            ]
        )

        with self.assertRaisesRegex(
            OpenWebUIClientError,
            "más de un modelo",
        ):
            client.export_model("epsilon")

    def test_updates_only_model_form_fields(
        self,
    ) -> None:
        model = self.build_model()
        client = RecordingOpenWebUIClient(
            response=model
        )

        result = client.update_model(model)

        self.assertEqual(result["id"], "epsilon")
        self.assertEqual(
            len(client.posts),
            1,
        )

        endpoint, payload = client.posts[0]

        self.assertEqual(
            endpoint,
            "/api/v1/models/model/update",
        )
        self.assertEqual(
            set(payload),
            {
                "id",
                "base_model_id",
                "name",
                "meta",
                "params",
                "access_grants",
                "is_active",
            },
        )
        self.assertNotIn("created_at", payload)
        self.assertNotIn("updated_at", payload)
        self.assertNotIn("user_id", payload)
        self.assertEqual(
            payload["meta"],
            model["meta"],
        )
        self.assertEqual(
            payload["params"],
            model["params"],
        )

    def test_update_can_omit_access_grants(
        self,
    ) -> None:
        model = self.build_model()
        client = RecordingOpenWebUIClient(
            response=model
        )

        client.update_model(
            model,
            include_access_grants=False,
        )

        endpoint, payload = client.posts[0]

        self.assertEqual(
            endpoint,
            "/api/v1/models/model/update",
        )
        self.assertNotIn(
            "access_grants",
            payload,
        )
        self.assertEqual(
            set(payload),
            {
                "id",
                "base_model_id",
                "name",
                "meta",
                "params",
                "is_active",
            },
        )

    def test_update_payload_is_a_deep_copy(
        self,
    ) -> None:
        model = self.build_model()
        client = RecordingOpenWebUIClient(
            response=model
        )

        client.update_model(model)

        payload = client.posts[0][1]
        payload["meta"]["knowledge"].clear()

        self.assertEqual(
            len(model["meta"]["knowledge"]),
            1,
        )

    def test_rejects_incomplete_model_forms(
        self,
    ) -> None:
        invalid_models = (
            self.build_model(id=""),
            self.build_model(name=""),
            self.build_model(meta=None),
            self.build_model(params=None),
            self.build_model(
                base_model_id=""
            ),
            self.build_model(
                access_grants="invalid"
            ),
            self.build_model(
                is_active="yes"
            ),
        )

        client = RecordingOpenWebUIClient()

        for invalid in invalid_models:
            with self.subTest(model=invalid):
                with self.assertRaises(ValueError):
                    client.update_model(invalid)

    def test_rejects_non_object_update_response(
        self,
    ) -> None:
        client = RecordingOpenWebUIClient(
            response=None
        )

        with self.assertRaisesRegex(
            OpenWebUIClientError,
            "no devolvió",
        ):
            client.update_model(
                self.build_model()
            )

    def test_rejects_update_response_for_other_model(
        self,
    ) -> None:
        client = RecordingOpenWebUIClient(
            response=self.build_model(
                id="other-model"
            )
        )

        with self.assertRaisesRegex(
            OpenWebUIClientError,
            "modelo diferente",
        ):
            client.update_model(
                self.build_model()
            )


if __name__ == "__main__":
    unittest.main()
