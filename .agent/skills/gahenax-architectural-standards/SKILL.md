---
name: "Gahenax Architectural Standards"
description: "Siempre utilízalo cuando se te asigne la tarea de escribir código nuevo, diseñar una arquitectura web o móvil, o revisar el código base de repositorios (Frontend o Backend) para auditar la calidad, asegurando que se adhiera a las heurísticas empresariales de Gahenax."
---

# GahenaxAI Architectural Standards

Basado en la biblia de heurísticas de ingeniería corporativa.

### Frontend
1. **React/Next.js:** Mantén fronteras RSC (React Server Components) estrictas. Pasa Server Components como `children` para prevenir fugas al cliente. Control férreo sobre linting de Hooks (Closure Traps).
2. **HTML/CSS:** Privilegia elementos semánticos de `<dialog>`, `<form>`. Diseño Macro = CSS Grid; Micro = Flexbox. Las UIs complejas no deben colapsar bajo "Div-Soups".
3. **Estilos:** En sistemas con Tailwind, si los bloques crecen en repetición, sepáralos como Componentes (e.g. `<Button>`), NUNCA asumas abusar de `@apply` en CSS, manteniendo utilidad-first puro.

### Backend y Base de Datos
1. **APIs (gRPC vs REST):** Norte-Sur es estrictamente REST/JSON. Este-Oeste entre microservicios intermedios es gRPC/Protobuf.
2. **Python ASGI:** ¡NUNCA bloquees el Event Loop! Tareas fuertes de AI van a celestiales (Workers). FastAPI solo encola descriptores.
3. **Bases de Datos Relacionales (MySQL):** Siempre llaves primarias SECUENCIALES (Incremental o UUIDv7) para proteger el índice B+ Tree agrupado. El `UUIDv4` está estrictamente prohibido para Primary Keys.
4. **PostgreSQL:** No satures con UPDATES hiper-frecuentes ya que activas penalizaciones de MVCC (Table Bloat).

**REGLA MAESTRA:** Cada pull request imaginario o implementación real que propongas, valídalo mentalmente contra este estándar. Si propones `UUIDv4` para MySQL, corrige automáticamente.
