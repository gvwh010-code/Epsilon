---
name: Research
description: Investiga, busca, comprueba y verifica información externa, actual o incierta usando búsqueda web y fuentes reales antes de responder.
---

# Research

## Objetivo

Obtener evidencia externa suficiente para responder con precisión.

La búsqueda descubre fuentes. La lectura de una fuente verifica hechos.

## Cuándo usar

Usa Research cuando el usuario pida investigar, buscar, comprobar o verificar información, o cuando la respuesta dependa de información actual o incierta.

Si la consulta también depende de un proyecto documentado en Knowledge, consulta primero el Knowledge relevante y después investiga únicamente lo externo.

## Flujo obligatorio

Para una investigación web:

1. Identifica los hechos centrales que necesitas comprobar.
2. Usa `search_web` para localizar fuentes.
3. Examina los resultados y selecciona la fuente más adecuada.
4. Antes de responder, usa `fetch_url` sobre al menos una fuente que sustente los hechos centrales, siempre que exista una fuente accesible.
5. Si existe una fuente primaria u oficial adecuada, priorízala.
6. Compara lo leído con la afirmación que vas a hacer.
7. Solo entonces responde.

`search_web` por sí solo no completa una investigación cuando la respuesta depende de hechos externos verificables.

No respondas basándote únicamente en títulos o snippets si puedes abrir una fuente relevante.

## Conflictos con conocimiento previo

La evidencia reciente no debe descartarse únicamente porque contradiga tu conocimiento interno.

Si un resultado actual contradice lo que recuerdas:

1. no elijas todavía ninguna de las dos versiones;
2. abre una fuente adecuada con `fetch_url`;
3. determina qué información corresponde a la fecha o versión actual;
4. responde según la evidencia verificada.

## Fuentes

Para hechos verificables, prioriza:

1. fuentes oficiales o primarias;
2. documentación;
3. publicaciones científicas o técnicas;
4. fuentes secundarias reputadas.

Reddit y foros son útiles para experiencias prácticas, problemas reales y opiniones, pero no sustituyen una fuente primaria cuando ésta existe.

No necesitas consultar varias fuentes si una fuente primaria responde claramente la pregunta. Contrasta más fuentes cuando haya contradicciones, ambigüedad o controversia.

## Causalidad e inferencias

No inventes explicaciones para completar información ausente.

Si el usuario pregunta por qué ocurrió algo, busca una fuente que trate directamente la causa.

Si una explicación es razonable pero no está documentada, identifícala como inferencia.

## Respuesta

Responde directamente.

Distingue cuando sea necesario entre:

- confirmado;
- inferencia;
- incierto.

No inventes nombres, fechas, versiones, cifras, autorías ni fuentes.

No afirmes haber consultado una fuente que no abriste.

Detén la investigación cuando exista evidencia suficiente.