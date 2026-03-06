---
name: "Skill Creator"
description: "Activa esta skill siempre que el usuario te pida crear una nueva 'skill', un protocolo, un workflow recurrente, o enseñarte un patrón permanente de razonamiento."
---

# Instalar y Crear Nuevas Skills (Basado en Anthropics/skills)

Cuando el usuario pida crear una nueva skill, sigue este preciso flujo:

### 1. Capturar Intención y Entrevista
- ¿Qué debe permitirle hacer esta skill a la IA?
- ¿Cuándo debería activarse? (¿Qué frases o contexto del usuario?)
- ¿Cuál es el formato de salida esperado?
- Revisa el historial de la conversación actual, tal vez el usuario ya hizo el flujo manualmente antes de pedirte que lo conviertas en skill.

### 2. Escribir el SKILL.md
La anatomía requerida para crear la skill en el directorio `.agent/skills/<nombre-skill>/` es:

```markdown
---
name: "[Nombre entendible]"
description: "[Instrucciones claras sobre CUÁNDO debe activarse la skill. Hazlo un poco 'agresivo' para que el modelo realmente la use cuando aplique el contexto, e.g. 'SIEMPRE úsalo cuando el usuario hable de X']"
---
[El contenido Markdown de la skill]
```

### 3. Reglas de Escritura
- Prefiere verbos imperativos.
- Usa jerarquía de Markdown clara.
- Usa la divulgación progresiva (Progressive Disclosure): mantén el `SKILL.md` de menos de 500 líneas. Si necesitas más, divide en archivos de referencia y enséñale al modelo en el SKILL.md cuándo y qué archivo cargar.
- Escribe ejemplos precisos de Input / Output si la skill trata de transformar formatos de texto o código.
- No uses `MUST` exageradamente; intenta explicarle al motor *por qué* las cosas son importantes (Theory of Mind).
