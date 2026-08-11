---
name: Research
description: Investiga, busca, comprueba y verifica información externa, actual o incierta mediante Epsilon Research.
---

# Research

## Objetivo

Obtener evidencia externa suficiente para responder con precisión utilizando
Epsilon Research como la ruta canónica de investigación del sistema.

La lógica de búsqueda, selección de fuentes, lectura, verificación y síntesis
pertenece al servicio Epsilon Research y no debe duplicarse desde OpenWebUI.

## Cuándo usar

Usa Research cuando:

- el usuario pida investigar, buscar, comprobar o verificar información;
- la respuesta dependa de información externa o actual;
- exista incertidumbre sobre un hecho que requiera evidencia;
- sea necesario respaldar una respuesta con fuentes web.

Si la consulta también depende de información disponible en Knowledge,
consulta primero el contexto relevante del proyecto y utiliza Research
solamente para aquello que requiera evidencia externa.

## Flujo obligatorio

Cuando sea necesaria investigación externa:

1. parte de la solicitud real del usuario, no de recuerdos internos sobre el tema;
2. formula una pregunta autosuficiente, completa y neutral;
3. llama normalmente una sola vez a la herramienta `research`;
4. espera el resultado completo de Epsilon Research;
5. utiliza ese resultado como frontera de evidencia para elaborar la respuesta final;
6. no añadas después hechos externos que Research no haya respaldado.

Ejemplo conceptual:

`research(question="¿Cuál es la versión estable actual de OpenWebUI y qué cambios principales incluye?")`

## Herramienta canónica

La herramienta `research` es la única ruta normal para realizar investigación
web desde Epsilon.

No reproduzcas manualmente dentro de OpenWebUI el proceso que ya realiza
Epsilon Research.

En particular, durante una investigación normal:

- no uses `search_web`;
- no uses `fetch_url`;
- no construyas manualmente cadenas de búsqueda y lectura web;
- no sustituyas silenciosamente Epsilon Research por otra herramienta web.

Epsilon Research ya se encarga internamente de:

- planificar búsquedas;
- consultar el motor de búsqueda;
- seleccionar candidatos;
- obtener fuentes;
- eliminar duplicados;
- priorizar evidencia;
- sintetizar la respuesta;
- incorporar citas y URLs.

## Uso eficiente

Una llamada a `research` ya constituye una investigación completa e incluye
internamente planificación, varias búsquedas, selección de fuentes, lectura,
verificación y síntesis.

No dividas una misma investigación en llamadas sucesivas solamente porque
recuerdes otro dato, nombre, fecha, anécdota, relación, causa o posible
explicación.

Realiza una llamada adicional solamente cuando:

- el usuario plantee una segunda pregunta realmente distinta;
- Research indique explícitamente que una parte esencial de la pregunta
  original quedó sin resolver;
- el usuario solicite ampliar o profundizar después del primer resultado.

## Fallos

Si `research` falla o no devuelve una respuesta utilizable:

- no inventes resultados;
- no afirmes haber investigado algo que no fue verificado;
- informa claramente que Epsilon Research no pudo completar la investigación.

No uses automáticamente `search_web` o `fetch_url` como mecanismo alternativo
sin una instrucción explícita que autorice ese fallback.

## Respuesta

Usa el resultado de Epsilon Research para responder directamente a la pregunta
del usuario.

Una vez utilizado Research, trata su resultado como la frontera factual para
la información externa de esa respuesta. Puedes organizar, resumir, comparar
y explicar la evidencia recuperada, pero no completar silenciosamente el
resultado con hechos procedentes únicamente de memoria interna.

Si Research no pudo verificar una afirmación, conserva esa incertidumbre en la
respuesta final.

Conserva las citas y fuentes relevantes proporcionadas por Research.

Distingue cuando sea necesario entre:

- información confirmada;
- inferencias;
- información que no pudo verificarse.

No inventes nombres, fechas, versiones, cifras, autorías, relaciones causales
ni fuentes.
