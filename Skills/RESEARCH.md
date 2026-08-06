---
name: Research
description: Investiga, busca, comprueba y verifica información externa, actual o incierta usando búsqueda web y fuentes reales antes de responder.
---

# Research

## Objetivo

Obtener evidencia externa suficiente para responder con precisión, evitando búsquedas redundantes y consumo innecesario de contexto.

La búsqueda descubre fuentes. La lectura de una fuente verifica hechos.

## Cuándo usar

Usa Research cuando el usuario pida investigar, buscar, comprobar o verificar información, o cuando la respuesta dependa de información actual o incierta.

Si la consulta también depende de un proyecto documentado en Knowledge, consulta primero el Knowledge relevante y después investiga únicamente lo externo.

## Presupuesto de investigación

Para una investigación normal:

- realiza inicialmente una sola búsqueda bien formulada;
- usa como máximo 3 llamadas a `search_web`;
- usa como máximo 2 llamadas a `fetch_url`;
- no repitas una búsqueda con términos casi equivalentes si los resultados existentes ya contienen candidatos adecuados;
- no abras varias fuentes que solo confirman exactamente el mismo hecho;
- detente antes de alcanzar estos límites si ya existe evidencia suficiente.

## Presupuesto de investigación

Para una investigación normal existe un límite estricto:

- máximo 3 llamadas a `search_web`;
- máximo 2 llamadas a `fetch_url`.

Estos límites no se superan aunque falte evidencia.

Si después de alcanzar el límite un hecho no pudo verificarse:

1. deja de usar herramientas;
2. no intentes nuevas variantes de búsqueda;
3. descarta cualquier hipótesis no verificada;
4. responde con la evidencia disponible;
5. indica claramente qué punto no pudiste confirmar.

Solo una petición explícita del usuario de investigación profunda o exhaustiva permite superar estos límites.

No uses búsquedas adicionales para intentar demostrar una hipótesis surgida de tu conocimiento interno.

Más búsquedas no implican una investigación mejor.

## Control de contexto

Protege la ventana de contexto durante investigaciones con herramientas.

- Prefiere páginas específicas sobre un hecho frente a páginas generales, archivos extensos, índices, feeds, transcripciones o páginas que puedan contener grandes cantidades de texto.
- Antes de abrir otra fuente, determina qué hecho concreto falta por verificar.
- Después de obtener una fuente suficiente para un hecho, no sigas acumulando fuentes sobre ese mismo hecho sin necesidad.
- Si una fuente abierta aporta una gran cantidad de contenido, no abras fuentes adicionales salvo que falte evidencia esencial.
- Prioriza evidencia relevante sobre cantidad de texto.
- No continúes investigando únicamente para enriquecer o alargar la respuesta.

## Flujo obligatorio

Para una investigación web:

1. Identifica los hechos centrales que necesitas comprobar.
2. Formula una búsqueda específica que pueda localizar evidencia para esos hechos.
3. Usa `search_web`.
4. Examina los resultados y selecciona la fuente más adecuada.
5. Antes de responder, usa `fetch_url` sobre al menos una fuente que sustente los hechos centrales, siempre que exista una fuente accesible.
6. Si existe una fuente primaria u oficial adecuada, priorízala.
7. Compara explícitamente lo leído con la afirmación que vas a hacer.
8. Si queda un hecho central sin verificar, realiza una búsqueda adicional dirigida únicamente a ese hecho.
9. Solo entonces responde.

`search_web` por sí solo no completa una investigación cuando la respuesta depende de hechos externos verificables.

Los títulos y snippets sirven para descubrir fuentes, no para confirmar hechos cuando puede abrirse una fuente relevante.

## Verificación

Una afirmación solo debe considerarse confirmada cuando una fuente consultada realmente la sustente.

No conviertas en hecho:

- una hipótesis surgida durante el razonamiento;
- una asociación basada solo en conocimiento interno;
- una afirmación vista únicamente en un snippet;
- una conclusión que la fuente no diga o no permita establecer claramente.

No uses expresiones como "confirmado", "está demostrado" o equivalentes si la evidencia correspondiente no fue abierta y comprobada.

Si una fuente verifica solo parte de una afirmación, limita la respuesta a esa parte.

## Conflictos con conocimiento previo

La evidencia reciente no debe descartarse únicamente porque contradiga tu conocimiento interno.

Si un resultado actual contradice lo que recuerdas:

1. no elijas todavía ninguna de las dos versiones;
2. abre una fuente adecuada con `fetch_url`;
3. determina qué información corresponde a la fecha o versión actual;
4. responde según la evidencia verificada.

Si no logras resolver la contradicción, indícala en lugar de completar el vacío mediante una suposición.

## Fuentes

Para hechos verificables, prioriza:

1. fuentes oficiales o primarias;
2. documentación;
3. publicaciones científicas o técnicas;
4. fuentes secundarias reputadas.

Reddit y foros son útiles para experiencias prácticas, problemas reales y opiniones, pero no sustituyen una fuente primaria cuando ésta existe.

No necesitas consultar varias fuentes si una fuente primaria responde claramente la pregunta.

Contrasta más fuentes cuando haya contradicciones, ambigüedad o controversia.

## Causalidad e inferencias

No inventes explicaciones para completar información ausente.

Si el usuario pregunta por qué ocurrió algo, busca una fuente que trate directamente la causa.

Si no encuentras evidencia directa de la causa:

- dilo;
- no continúes buscando indefinidamente;
- si existe una explicación razonable, identifícala explícitamente como inferencia.

## Respuesta

Responde directamente y proporcionalmente a la pregunta.

Distingue cuando sea necesario entre:

- confirmado;
- inferencia;
- incierto.

No inventes nombres, fechas, versiones, cifras, autorías, relaciones causales ni fuentes.

No afirmes haber consultado una fuente que no abriste.

No incluyas hechos accesorios que no sean necesarios para responder si no fueron verificados.

Detén la investigación tan pronto exista evidencia suficiente para responder los hechos centrales.
