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

1. identifica qué pregunta concreta debe investigarse;
2. llama a la herramienta `research`;
3. formula en `question` una pregunta autosuficiente que describa claramente
   lo que debe investigarse;
4. espera el resultado de Epsilon Research;
5. utiliza ese resultado como evidencia para elaborar la respuesta final.

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

Una llamada a `research` debe contener una pregunta suficientemente completa
para que el servicio pueda investigar el problema de principio a fin.

Evita dividir innecesariamente una misma investigación en múltiples llamadas.

Realiza una llamada adicional solamente cuando:

- aparezca una segunda pregunta realmente distinta;
- el resultado indique explícitamente que falta un aspecto esencial;
- el usuario solicite ampliar o profundizar la investigación.

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

Conserva las citas y fuentes relevantes proporcionadas por Research.

Distingue cuando sea necesario entre:

- información confirmada;
- inferencias;
- información que no pudo verificarse.

No inventes nombres, fechas, versiones, cifras, autorías, relaciones causales
ni fuentes.
