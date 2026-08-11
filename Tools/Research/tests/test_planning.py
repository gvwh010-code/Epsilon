from __future__ import annotations

import unittest

from Tools.Research.planning import (
    build_research_plan,
)


class PlanningTests(unittest.TestCase):
    def test_removes_conversational_wrapper(self):
        plan = build_research_plan(
            (
                "Háblame de Sonic Youth y su "
                "relación con Nirvana. "
                "Investiga bien y me cuentas."
            )
        )

        self.assertEqual(
            plan.queries[0],
            "Sonic Youth Nirvana",
        )

    def test_does_not_inject_specific_facts(self):
        plan = build_research_plan(
            "Sonic Youth Nirvana"
        )

        combined = " ".join(
            plan.queries
        ).lower()

        self.assertNotIn(
            "nevermind",
            combined,
        )

        self.assertNotIn(
            "kurt cobain",
            combined,
        )

        self.assertNotIn(
            "thurston moore",
            combined,
        )

    def test_normalizes_whitespace(self):
        plan = build_research_plan(
            "  climate    change  "
        )

        self.assertEqual(
            plan.queries[0],
            "climate change",
        )

    def test_preserves_meaningful_terms(self):
        plan = build_research_plan(
            (
                "Investiga el impacto de la "
                "inteligencia artificial en medicina"
            )
        )

        self.assertEqual(
            plan.queries[0],
            (
                "impacto inteligencia "
                "artificial medicina"
            ),
        )

    def test_empty_question_is_rejected(self):
        with self.assertRaises(
            ValueError
        ):
            build_research_plan("   ")

    def test_catalog_subject_removes_question_scaffolding(
        self,
    ):
        plan = build_research_plan(
            (
                "Investiga en la web si "
                "Sixpence None The Richer "
                "tiene canciones o versiones "
                "oficiales en español."
            )
        )

        self.assertEqual(
            plan.queries[0],
            '"Sixpence None The Richer" Spanish songs',
        )

        self.assertEqual(
            plan.queries[1],
            (
                '"Sixpence None The Richer" '
                'official Spanish versions'
            ),
        )

        self.assertEqual(
            plan.queries[2],
            (
                '"Sixpence None The Richer" '
                'discography track listing Spanish'
            ),
        )


if __name__ == "__main__":
    unittest.main()


class AspectPlanningTests(unittest.TestCase):
    def test_separates_topic_from_aspects(self):
        plan = build_research_plan(
            (
                "Investiga la relación entre Linux "
                "y GNU: su historia, qué aportó "
                "cada proyecto y sus principales "
                "diferencias. Explícamelo con fuentes."
            )
        )

        self.assertEqual(
            plan.queries,
            (
                "Linux GNU",
                "Linux GNU history",
                (
                    "Linux GNU history "
                    "contributions differences"
                ),
            ),
        )

    def test_simple_relation_needs_only_topic_query(
        self,
    ):
        plan = build_research_plan(
            (
                "Háblame de Sonic Youth y su "
                "relación con Nirvana. "
                "Investiga bien y me cuentas."
            )
        )

        self.assertEqual(
            plan.queries,
            ("Sonic Youth Nirvana",),
        )



class SourceModePlanningTests(unittest.TestCase):
    def test_default_source_mode_is_factual(self):
        plan = build_research_plan(
            "Sonic Youth Nirvana relationship"
        )
        self.assertEqual(
            plan.source_mode,
            "factual",
        )

    def test_detects_community_source_mode(self):
        plan = build_research_plan(
            "What do people think about systemd on Reddit and forums?"
        )
        self.assertEqual(
            plan.source_mode,
            "community",
        )

    def test_detects_mixed_source_mode(self):
        plan = build_research_plan(
            "What happened with systemd and what do people think about it?"
        )
        self.assertEqual(
            plan.source_mode,
            "mixed",
        )


class ResearchFocusTests(unittest.TestCase):
    def test_openwebui_instructions_do_not_pollute_query(
        self,
    ):
        clean = build_research_plan(
            (
                "qué piensa la gente sobre systemd "
                "en Reddit y foros"
            )
        )

        decorated = build_research_plan(
            (
                "Investiga en la web qué piensa la gente "
                "sobre systemd en Reddit y foros. "
                "Usa Epsilon Research, distingue claramente "
                "opiniones de hechos y cita las fuentes "
                "utilizadas."
            )
        )

        self.assertEqual(
            decorated.source_mode,
            "community",
        )

        self.assertEqual(
            decorated.queries,
            clean.queries,
        )

    def test_orchestration_words_are_not_search_terms(
        self,
    ):
        plan = build_research_plan(
            (
                "Investiga en la web qué piensa la gente "
                "sobre systemd en Reddit y foros. "
                "Usa Epsilon Research y cita las fuentes."
            )
        )

        query = " ".join(
            plan.queries
        ).lower()

        self.assertIn(
            "systemd",
            query,
        )
        self.assertIn(
            "reddit",
            query,
        )
        self.assertNotIn(
            "epsilon",
            query,
        )
        self.assertNotIn(
            "utilizadas",
            query,
        )

    def test_real_mixed_request_stays_mixed(
        self,
    ):
        plan = build_research_plan(
            (
                "Qué piensa la gente sobre systemd "
                "y qué evidencia existe sobre "
                "sus problemas"
            )
        )

        self.assertEqual(
            plan.source_mode,
            "mixed",
        )




class CatalogPlanningTests(unittest.TestCase):
    def test_music_catalog_question_gets_catalog_queries(
        self,
    ):
        plan = build_research_plan(
            (
                "Sixpence None The Richer "
                "canciones en español o "
                "versiones en español"
            )
        )

        joined = "\n".join(
            plan.queries
        ).lower()

        self.assertEqual(
            plan.source_mode,
            "factual",
        )

        self.assertEqual(
            len(plan.queries),
            3,
        )

        self.assertIn(
            "sixpence",
            joined,
        )

        self.assertTrue(
            (
                "discography"
                in joined
            )
            or (
                "track list"
                in joined
            )
        )

    def test_catalog_query_keeps_language(
        self,
    ):
        plan = build_research_plan(
            (
                "¿Tiene Sixpence None The Richer "
                "canciones en español?"
            )
        )

        self.assertTrue(
            any(
                "spanish"
                in query.lower()
                for query
                in plan.queries
            )
        )

    def test_specific_catalog_item_keeps_title_and_artist(
        self,
    ):
        plan = build_research_plan(
            (
                'Investiga sobre la canción '
                '"Puedo Escribir" de '
                'Sixpence None The Richer '
                'y dime más detalles.'
            )
        )

        self.assertEqual(
            plan.queries,
            (
                '"Puedo Escribir" "Sixpence None The Richer"',
                '"Sixpence None The Richer" "Puedo Escribir" song',
                '"Sixpence None The Richer" "Puedo Escribir" official releases',
            ),
        )

    def test_exhaustive_catalog_item_without_quotes(
        self,
    ):
        plan = build_research_plan(
            (
                "Investiga a fondo sobre Leigh Nash, "
                "la vocalista de Sixpence None The Richer, "
                "y si hay información relacionada con cómo "
                "canta la canción Puedo Escribir en español."
            )
        )

        self.assertEqual(
            plan.queries,
            (
                '"Leigh Nash" "Puedo Escribir"',
                '"Leigh Nash" "Puedo Escribir" interview',
                '"Leigh Nash" "Puedo Escribir" Spanish pronunciation',
            ),
        )

    def test_non_catalog_question_is_unchanged(
        self,
    ):
        plan = build_research_plan(
            (
                "What do people think about "
                "systemd on Reddit and forums?"
            )
        )

        self.assertEqual(
            plan.source_mode,
            "community",
        )

        self.assertFalse(
            any(
                "discography"
                in query.lower()
                for query
                in plan.queries
            )
        )


