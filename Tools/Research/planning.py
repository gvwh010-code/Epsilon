from __future__ import annotations

import re

from .models import ResearchPlan


_INSTRUCTION_STOPWORDS = {
    # Español
    "a", "al", "algo", "bien", "cada",
    "como", "cómo", "con", "cual", "cuál",
    "cuenta", "cuentas", "cuéntame", "cuentame",
    "de", "del", "dime", "el", "en", "entre",
    "es", "esta", "este", "esto",
    "explica", "explícame", "explicame",
    "explícamelo", "explicamelo",
    "fuente", "fuentes",
    "háblame", "hablame",
    "investiga", "investigar",
    "investigación", "investigacion",
    "la", "las", "lo", "los", "me",
    "o", "para", "por",
    "principal", "principales",
    "proyecto", "proyectos",
    "que", "qué",
    "relación", "relacion",
    "se", "sobre", "su", "sus",
    "un", "una", "unos", "unas", "y",

    # Inglés
    "a", "about", "an", "and", "are",
    "between", "can", "explain", "for",
    "from", "how", "in", "investigate",
    "is", "me", "of", "on", "or",
    "please", "project", "projects",
    "relation", "relationship",
    "research", "source", "sources",
    "tell", "the", "this", "to",
    "what", "with", "you",
}


_ASPECT_MAP = {
    # Historia / origen
    "historia": "history",
    "history": "history",
    "origen": "history",
    "orígenes": "history",
    "origenes": "history",
    "origin": "history",
    "origins": "history",
    "evolución": "history",
    "evolucion": "history",
    "evolution": "history",

    # Aportes / contribuciones
    "aporte": "contributions",
    "aportes": "contributions",
    "aportó": "contributions",
    "aporto": "contributions",
    "contribución": "contributions",
    "contribucion": "contributions",
    "contribuciones": "contributions",
    "contribution": "contributions",
    "contributions": "contributions",
    "contributed": "contributions",

    # Diferencias / comparación
    "diferencia": "differences",
    "diferencias": "differences",
    "difference": "differences",
    "differences": "differences",
    "comparación": "differences",
    "comparacion": "differences",
    "comparison": "differences",
    "comparar": "differences",
    "compare": "differences",

    # Causas
    "causa": "causes",
    "causas": "causes",
    "cause": "causes",
    "causes": "causes",

    # Efectos
    "efecto": "effects",
    "efectos": "effects",
    "effect": "effects",
    "effects": "effects",

    # Riesgos
    "riesgo": "risks",
    "riesgos": "risks",
    "risk": "risks",
    "risks": "risks",

    # Beneficios
    "beneficio": "benefits",
    "beneficios": "benefits",
    "benefit": "benefits",
    "benefits": "benefits",
}



_MUSIC_CATALOG_TERMS = {
    "canción",
    "cancion",
    "canciones",
    "song",
    "songs",
    "tema",
    "temas",
    "versión",
    "version",
    "versiones",
    "versions",
    "álbum",
    "album",
    "albums",
    "discografía",
    "discografia",
    "discography",
    "grabación",
    "grabacion",
    "grabaciones",
    "recording",
    "recordings",
}

_LANGUAGE_TERMS = {
    "español",
    "spanish",
    "inglés",
    "ingles",
    "english",
    "francés",
    "frances",
    "french",
    "alemán",
    "aleman",
    "german",
    "italiano",
    "italian",
    "portugués",
    "portugues",
    "portuguese",
}

_LANGUAGE_QUERY_LABELS = {
    "español": "Spanish",
    "spanish": "Spanish",
    "inglés": "English",
    "ingles": "English",
    "english": "English",
    "francés": "French",
    "frances": "French",
    "french": "French",
    "alemán": "German",
    "aleman": "German",
    "german": "German",
    "italiano": "Italian",
    "italian": "Italian",
    "portugués": "Portuguese",
    "portugues": "Portuguese",
    "portuguese": "Portuguese",
}

_CATALOG_SUBJECT_STOPWORDS = {
    "si",
    "sí",
    "tiene",
    "tienen",
    "tener",
    "hay",
    "existe",
    "existen",
    "algún",
    "algun",
    "alguna",
    "algunos",
    "algunas",
    "oficial",
    "oficiales",
    "en",
    "de",
    "del",
    "por",
    "parte",
    "una",
    "uno",
    "un",
    "la",
    "las",
    "los",
    "el",
    "que",
    "qué",
    "y",
    "o",
    "does",
    "do",
    "has",
    "have",
    "any",
    "official",
    "in",
    "of",
    "by",
    "or",
}


def _catalog_query_context(
    question: str,
) -> tuple[str, str] | None:
    catalog_question = re.split(
        (
            r"[?？;]"
            r"|\b(?:y\s+)?si\s+es\s+as[ií]\b"
            r"|\b(?:and\s+)?if\s+so\b"
        ),
        question,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]

    words = re.findall(
        r"[^\W_]+",
        catalog_question,
        flags=re.UNICODE,
    )

    lowered_words = {
        word.lower()
        for word in words
    }

    performance_cues = (
        "cómo canta",
        "como canta",
        "cómo interpreta",
        "como interpreta",
        "pronunciación",
        "pronunciacion",
        "técnica vocal",
        "tecnica vocal",
        "vocalista",
        "entrevista",
        "interview",
        "how she sings",
        "how he sings",
        "vocal technique",
        "pronunciation",
    )

    normalized_question = question.lower()

    if any(
        cue in normalized_question
        for cue in performance_cues
    ):
        return None

    if not (
        lowered_words
        & _MUSIC_CATALOG_TERMS
    ):
        return None

    languages = [
        word.lower()
        for word in words
        if word.lower()
        in _LANGUAGE_TERMS
    ]

    subject_words = [
        word
        for word in words
        if (
            word.lower()
            not in _MUSIC_CATALOG_TERMS
            and word.lower()
            not in _LANGUAGE_TERMS
            and word.lower()
            not in _CATALOG_SUBJECT_STOPWORDS
        )
    ]

    subject = " ".join(
        dict.fromkeys(subject_words)
    ).strip()

    if not subject:
        return None

    language = ""

    if languages:
        language = _LANGUAGE_QUERY_LABELS.get(
            languages[0],
            languages[0],
        )

    return subject, language



def _catalog_item_query_context(
    question: str,
) -> tuple[str, str] | None:
    words = {
        word.lower()
        for word in re.findall(
            r"[^\W_]+",
            question,
            flags=re.UNICODE,
        )
    }

    if not (words & _MUSIC_CATALOG_TERMS):
        return None

    match = re.search(
        r'["“]([^"”]{2,160})["”]\s+'
        r'(?:de|by)\s+(.+)',
        question,
        flags=re.IGNORECASE,
    )

    if not match:
        return None

    title = match.group(1).strip()
    artist = match.group(2).strip()

    artist = re.split(
        r"\s+(?:y\s+)?(?:dime|cuéntame|cuentame)"
        r"\b|\s+(?:más|mas)\s+detalles\b",
        artist,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0].strip(" .,:;!?")

    if not title or not artist:
        return None

    return title, artist


_COMMUNITY_CUES = (
    "qué piensa la gente",
    "que piensa la gente",
    "qué opina la gente",
    "que opina la gente",
    "opinión de la gente",
    "opinion de la gente",
    "opiniones de la gente",
    "opiniones de usuarios",
    "qué dicen los usuarios",
    "que dicen los usuarios",
    "experiencias de usuarios",
    "experiencias de personas",
    "en reddit",
    "en foros",
    "redes sociales",
    "what do people think",
    "what people think",
    "what do users think",
    "what users think",
    "what are people saying",
    "what people are saying",
    "user opinions",
    "user experiences",
    "on reddit",
    "on forums",
    "social media",
    "community opinion",
    "community opinions",
)

_FACTUAL_CUES = (
    "qué pasó",
    "que paso",
    "qué ocurrió",
    "que ocurrio",
    "what happened",
    "what occurred",
    "historia",
    "history",
    "historical",
    "evidencia",
    "evidence",
    "hechos",
    "facts",
    "fuente oficial",
    "official source",
    "estudios",
    "studies",
)


def _detect_source_mode(
    question: str,
) -> str:
    normalized = " ".join(
        question.lower().split()
    )

    community = any(
        cue in normalized
        for cue in _COMMUNITY_CUES
    )

    factual = any(
        cue in normalized
        for cue in _FACTUAL_CUES
    )

    if community and factual:
        return "mixed"

    if community:
        return "community"

    return "factual"


def _normalize_question(
    question: str,
) -> str:
    return " ".join(
        question.split()
    ).strip()


def _extract_research_focus(
    question: str,
) -> str:
    """
    Conserva el contenido que debe investigarse y
    elimina instrucciones explícitas de orquestación
    o presentación que no pertenecen a la búsqueda.
    """

    normalized = _normalize_question(
        question
    )

    if not normalized:
        return ""

    # Quita únicamente órdenes explícitas que
    # introducen Research. El contenido posterior
    # sigue siendo la pregunta real.
    prefix_pattern = re.compile(
        r"^(?:por favor[, ]+)?(?:"
        r"investiga(?:r)?(?:\s+en\s+(?:la\s+)?"
        r"(?:web|internet))?"
        r"|busca(?:r)?\s+en\s+(?:la\s+)?"
        r"(?:web|internet)"
        r"|verifica(?:r)?\s+en\s+internet"
        r"|comprueba(?:r)?\s+en\s+internet"
        r"|search\s+(?:the\s+)?web"
        r"|search\s+online"
        r"|look\s+up\s+online"
        r"|research\s+this"
        r")\s*[:,\-]?\s*",
        flags=re.IGNORECASE,
    )

    normalized = prefix_pattern.sub(
        "",
        normalized,
        count=1,
    ).strip()

    # Separamos solo cuando aparece una nueva
    # instrucción claramente operativa.
    clauses = re.split(
        r"(?<=[.!?;])\s+"
        r"|,\s*(?="
        r"(?:usa|use|cita|cite|"
        r"distingue|distinguish|"
        r"separa|separate)\b)",
        normalized,
        flags=re.IGNORECASE,
    )

    kept: list[str] = []

    for clause in clauses:
        clause = clause.strip(
            " \t\r\n.,;:"
        )

        if not clause:
            continue

        lowered = " ".join(
            clause.lower().split()
        )

        if re.match(
            r"^(?:usa|use)\s+"
            r"(?:epsilon\s+research|"
            r"la\s+herramienta|the\s+tool)\b",
            lowered,
        ):
            continue

        if (
            re.match(
                r"^(?:cita|cite|incluye|include)\b",
                lowered,
            )
            and re.search(
                r"\b(?:fuente|fuentes|source|sources|"
                r"url|urls|enlace|enlaces|link|links)\b",
                lowered,
            )
        ):
            continue

        if re.match(
            r"^(?:distingue|distinguish|"
            r"separa|separate)\b",
            lowered,
        ):
            has_opinion = re.search(
                r"\b(?:opinion|opinión|opiniones|"
                r"opinions?)\b",
                lowered,
            )
            has_fact = re.search(
                r"\b(?:hecho|hechos|facts?)\b",
                lowered,
            )

            if has_opinion and has_fact:
                continue

        kept.append(clause)

    focus = " ".join(
        kept
    ).strip()

    return focus or normalized


def _extract_topic_and_aspects(
    question: str,
) -> tuple[str, tuple[str, ...]]:
    words = re.findall(
        r"[^\W_]+",
        question,
        flags=re.UNICODE,
    )

    topic_terms: list[str] = []
    aspects: list[str] = []

    seen_topic: set[str] = set()
    seen_aspects: set[str] = set()

    for word in words:
        lowered = word.lower()

        aspect = _ASPECT_MAP.get(
            lowered
        )

        if aspect is not None:
            if aspect not in seen_aspects:
                seen_aspects.add(aspect)
                aspects.append(aspect)
            continue

        if lowered in _INSTRUCTION_STOPWORDS:
            continue

        if len(word) < 2:
            continue

        if lowered in seen_topic:
            continue

        seen_topic.add(lowered)
        topic_terms.append(word)

        if len(topic_terms) >= 16:
            break

    topic = " ".join(
        topic_terms
    ).strip()

    if not topic:
        topic = _normalize_question(
            question
        )

    return topic, tuple(
        aspects[:4]
    )


def build_research_plan(
    question: str,
) -> ResearchPlan:
    """
    Construye consultas deterministas.

    La primera consulta identifica el tema.
    Las siguientes solo incorporan aspectos
    explícitamente pedidos por el usuario.
    """

    normalized = _normalize_question(
        question
    )

    if not normalized:
        raise ValueError(
            "La pregunta de investigación "
            "está vacía."
        )

    focus = _extract_research_focus(
        normalized
    )

    source_mode = _detect_source_mode(
        focus
    )

    topic, aspects = (
        _extract_topic_and_aspects(
            focus
        )
    )

    exhaustive = any(
        cue in focus.lower()
        for cue in (
            "exhaustiva",
            "exhaustivo",
            "exhaustivamente",
            "a fondo",
            "in depth",
            "thorough",
        )
    )

    if exhaustive:
        quoted = re.findall(
            r'["“\']([^"”\']{2,160})["”\']',
            focus,
        )

        names = re.findall(
            r'\b[A-ZÁÉÍÓÚÑ][\w’\'-]*'
            r'(?:\s+[A-ZÁÉÍÓÚÑ][\w’\'-]*){1,5}\b',
            focus,
        )

        title = quoted[0] if quoted else ""

        if not title:
            unquoted_title = re.search(
                r"\b(?:canción|cancion|song)\s+"
                r"([A-ZÁÉÍÓÚÑ][\w’'-]*"
                r"(?:\s+[A-ZÁÉÍÓÚÑ][\w’'-]*){1,5})"
                r"(?=\s+(?:en|in|de|by)\b|[,.?;]|$)",
                focus,
            )

            if unquoted_title:
                title = unquoted_title.group(1).strip()

        names = [
            name
            for name in names
            if name != title
        ]

        if title and names:
            subject = names[0]

            queries = [
                f'"{subject}" "{title}"',
                f'"{subject}" "{title}" interview',
                f'"{subject}" "{title}" Spanish pronunciation',
            ]

            return ResearchPlan(
                queries=tuple(queries),
                verification_targets=(),
                source_mode=source_mode,
            )

    item_context = (
        _catalog_item_query_context(
            focus
        )
    )

    catalog_context = (
        _catalog_query_context(
            focus
        )
    )

    if item_context is not None:
        title, artist = item_context

        queries = [
            f'"{title}" "{artist}"',
            f'"{artist}" "{title}" song',
            (
                f'"{artist}" "{title}" '
                "official releases"
            ),
        ]

    elif catalog_context is not None:
        subject, language = catalog_context
        quoted_subject = f'"{subject}"'

        if language:
            queries: list[str] = [
                f"{quoted_subject} {language} songs",
                (
                    f"{quoted_subject} "
                    f"official {language} versions"
                ),
                (
                    f"{quoted_subject} "
                    f"discography track listing "
                    f"{language}"
                ),
            ]
        else:
            queries = [
                topic,
                (
                    f"{quoted_subject} "
                    f"discography track listing"
                ),
                f"{quoted_subject} official releases",
            ]
    else:
        queries = [
            topic,
        ]

    if aspects:
        queries.append(
            f"{topic} {aspects[0]}"
        )

        combined = (
            f"{topic} "
            + " ".join(aspects)
        )

        if combined not in queries:
            queries.append(
                combined
            )

    return ResearchPlan(
        queries=tuple(queries[:3]),
        verification_targets=(),
        source_mode=source_mode,
    )
