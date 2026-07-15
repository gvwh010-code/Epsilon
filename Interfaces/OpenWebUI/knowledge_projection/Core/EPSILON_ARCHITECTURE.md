# Epsilon Architecture

## 1. Objetivo de la arquitectura

Epsilon debe funcionar como un asistente personal general, local, modular y portable.

Su identidad, conocimiento y forma de trabajo no deben depender de:

- un modelo específico;
- una interfaz específica;
- Windows o Linux;
- un proveedor externo;
- una sola herramienta.

Cada componente debe tener una responsabilidad clara y poder ser reemplazado sin reconstruir todo el sistema.

---

## 2. Arquitectura general

```text
Usuario
   │
   ▼
Open WebUI
   │
   ▼
Epsilon
   ├── Core
   ├── Skills
   ├── Knowledge
   ├── Memory
   └── Tools
   │
   ▼
Modelo local
   │
   ▼
Ollama