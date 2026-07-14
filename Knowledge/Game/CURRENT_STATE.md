# Estado actual del proyecto

## Objetivo principal

Desarrollar un roguelite 3D escalable en Godot mediante sistemas pequeños, estables y fáciles de mantener.

---

## Sistema actualmente en desarrollo

Dungeon Logic.

Actualmente el trabajo está centrado en la representación lógica del dungeon y en preparar la siguiente etapa de generación.

---

## Estado confirmado

Los siguientes sistemas ya funcionan correctamente o se consideran suficientemente estables para continuar:

- generación de pisos;
- generación de habitaciones;
- asignación de tipos de habitación;
- conexiones entre habitaciones;
- generación principal de pasillos;
- validación de habitaciones conectadas;
- cámaras de habitaciones;
- movimiento relativo a la cámara;
- DungeonLogicMap;
- DungeonAnalyzer;
- DungeonDebug;
- modo espectador;
- estructura general del proyecto;
- control mediante Git.

---

## Pendiente inmediato

Determinar correctamente las zonas outside y continuar desarrollando la lógica del dungeon.

---

## Restricciones actuales

No modificar:

- sistemas estables sin necesidad;
- cámaras de habitaciones;
- arquitectura principal de generación.

Los cambios deben ser pequeños y verificables.

---

## Problemas conocidos

Las zonas outside todavía requieren una solución definitiva.

Las cámaras automáticas para pasillos aún no forman parte del sistema final.

---

## Última decisión importante

Antes de seguir agregando nuevos sistemas, se priorizará terminar correctamente la lógica del dungeon.

---

## Próximo objetivo

Finalizar la lógica necesaria para outside y continuar con el siguiente sistema del roadmap.

---

## Recordatorio para Epsilon

Antes de proponer código:

- revisar el objetivo actual;
- identificar los scripts involucrados;
- conservar los sistemas estables;
- proponer el cambio mínimo;
- esperar el resultado de la prueba antes de asumir que la solución funciona.