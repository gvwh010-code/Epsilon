# Contexto permanente del videojuego

## Concepto general

El proyecto es un videojuego roguelite 3D para un jugador desarrollado en Godot.

Combina:

- progresión, objetos y sinergias inspiradas en The Binding of Isaac;
- combate más comprometido, con cierta influencia soulslike;
- generación procedural de habitaciones y pasillos;
- cámaras fijas inspiradas en Resident Evil;
- una atmósfera liminal, dreamcore, extraña y familiar.

No es un juego de terror puro.

La sensación buscada es:

- misteriosa;
- inquietante;
- triste pero acogedora;
- extraña pero reconocible;
- similar a un recuerdo confuso o un lugar visto en un sueño.

Las referencias visuales incluyen:

- espacios liminales;
- backrooms;
- Jack Stauber;
- juguetes antiguos;
- figuras plásticas;
- estética infantil envejecida.

## Objetivo del proyecto

Construir primero una demo jugable completa, estable y expandible.

La prioridad no es crear desde el comienzo todos los sistemas posibles, sino completar un ciclo jugable funcional que luego pueda crecer.

La arquitectura debe permitir agregar contenido sin tener que rehacer constantemente los sistemas principales.

## Principios de diseño

### Simplicidad

El combate debe mantenerse relativamente simple.

No se deben agregar sistemas complejos solo porque sean técnicamente interesantes.

### Escalabilidad práctica

Los sistemas deben poder crecer, pero no deben ser excesivamente abstractos ni difíciles de depurar.

### Cambios controlados

Los sistemas que ya funcionan deben conservarse.

Los problemas localizados deben resolverse mediante cambios pequeños siempre que sea posible.

### Validación

Una generación procedural inválida debe descartarse y reiniciarse.

No se deben aceptar pisos con habitaciones desconectadas o rutas que atraviesen habitaciones incorrectamente.

### Pasillos importantes

Los pasillos no son solo conexiones entre salas.

Forman parte central de la exploración, la atmósfera y la estructura del nivel.

### Aprendizaje

El usuario está aprendiendo programación mientras desarrolla el proyecto.

Las soluciones deben ser comprensibles y explicadas.

## Tecnología

Motor:

- Godot 4.x.

Versiones utilizadas:

- Godot 4.6.1;
- Godot 4.7.

Lenguaje principal:

- GDScript.

Herramientas complementarias:

- Blender para arte y modelos;
- Git para control de versiones;
- VS Code como editor auxiliar.

## Estructura general del dungeon

El dungeon está compuesto por dos pisos conectados.

Cada piso:

- ocupa aproximadamente un área de 70 x 70 unidades;
- contiene habitaciones colocadas proceduralmente;
- utiliza pasillos para conectarlas;
- tiene muros exteriores;
- debe ser completamente recorrible;
- puede incluir una zona exterior o secreta.

Las habitaciones pueden encontrarse relativamente cerca o tocarse visualmente si la generación lo permite.

La intención es crear una estructura similar a una casa antigua o un espacio interior irregular, no una cuadrícula rígida de habitaciones separadas.

## Tipos de habitaciones

Los tipos actuales incluyen:

- SPAWN;
- NORMAL;
- ITEM_1;
- ITEM_2;
- BOSS_1;
- BOSS_2;
- EXCHANGE;
- CHALLENGE;
- THEMATIC_1;
- THEMATIC_2;
- VERTICAL.

Cada piso debe incluir determinados tipos obligatorios.

Las habitaciones especiales deben distribuirse correctamente entre ambos pisos.

## Arquitectura general

Los sistemas principales incluyen:

### FloorGenerator

Responsable de generar cada piso.

Instancia habitaciones, solicita las conexiones, genera pasillos y coordina la construcción final del dungeon.

### Room

Representa una habitación.

Contiene dimensiones, tipo y paredes interiores.

### DungeonLayout

Genera la estructura lógica de conexiones entre habitaciones.

### CorridorGenerator

Calcula y construye los pasillos entre habitaciones.

Utiliza una cuadrícula y rutas Manhattan mediante A*.

También gestiona entradas, puertas y conectores.

### DungeonLogicMap

Construye una representación lógica del dungeon final mediante celdas.

Registra:

- habitaciones;
- pasillos;
- puertas;
- espacios caminables;
- espacios bloqueados;
- conexiones cardinales.

### DungeonAnalyzer

Analiza la geometría y la topología de las celdas.

Puede clasificar:

- extremos;
- rectas;
- esquinas;
- intersecciones.

### DungeonDebug

Visualiza la información de DungeonLogicMap y DungeonAnalyzer.

Permite revisar geometría, topología y redes caminables.

### CameraManager

Administra cámaras fijas.

Las cámaras de habitaciones ya utilizan zonas y markers.

Las cámaras de pasillos todavía no tienen una solución definitiva.

### Player

Controla al personaje.

El movimiento es relativo a la cámara activa.

## Reglas técnicas importantes

- El tamaño de celda estable de CorridorGenerator es 7.0.
- Los pasillos no deben atravesar habitaciones.
- Ninguna habitación puede quedar desconectada.
- Una generación inválida debe reiniciarse.
- Las cámaras de habitaciones que ya funcionan no deben modificarse sin una necesidad clara.
- Las cámaras automáticas de pasillos anteriores fueron descartadas.
- La representación lógica debe reflejar el dungeon final real.
- La geometría visual y la representación lógica son sistemas relacionados, pero no idénticos.
- No se deben rehacer sistemas completos para corregir problemas visuales menores.
- Git debe utilizarse antes de cambios importantes.

## Metodología de desarrollo

El trabajo se realiza por sistemas pequeños.

El ciclo habitual es:

1. definir el objetivo;
2. revisar el código actual;
3. proponer un cambio pequeño;
4. implementar manualmente;
5. probar en Godot;
6. observar el resultado;
7. corregir o confirmar;
8. guardar un estado estable mediante Git;
9. continuar con el siguiente objetivo.

No se considera que una solución funcione hasta que haya sido probada.

## Alcance futuro

El proyecto deberá incluir posteriormente:

- combate;
- enemigos;
- vida y daño;
- armas;
- objetos;
- sinergias;
- jefes;
- contenido de habitaciones;
- recompensas;
- interfaz;
- guardado;
- audio;
- animaciones;
- balance;
- optimización;
- exportación.

Estos sistemas deben agregarse progresivamente.

No deben implementarse todos simultáneamente.