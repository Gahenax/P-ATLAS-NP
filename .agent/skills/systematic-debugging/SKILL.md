---
name: "Systematic Debugging"
description: "Usa esta skill rigurosamente SIEMPRE que te encuentres con un bug difícil, una prueba unitaria fallando, un error en producción, un problema de rendimiento, o cuando iteraciones anteriores intentando resolver un problema no hayan funcionado."
---

# Systematic Debugging (La Ley de Hierro)

Los parches rápidos ocultan los problemas subyacentes y desperdician tiempo.

## LA LEY DE HIERRO
**CERO ARREGLOS SIN INVESTIGAR LA CAUSA RAÍZ PRIMERO.**
Si no has completado la Fase 1, no tienes permiso para proponer cambios de código o arreglos.

## Las 4 Fases (Debes completarlas secuencialmente)

### Fase 1: Investigación de Causa Raíz (Root Cause)
1. **Lee Cuidadosamente:** No descartes los warnings. Lee el Stack Trace completo.
2. **Reproducibilidad:** ¿Puede gatillarse siempre? ¿Cuáles son los pasos? Si no es reproducible, recopila datos empíricos, no adivines.
3. **Cambios Recientes:** ¿Qué cambió (git diff, dependencias) justo antes de que se rompiera?
4. **Instrumentación (Sistemas multicomponente):** Antes de arreglar, ANTES de hipotetizar, añade instrumentación de logs (print, console.log) para evidenciar QUÉ componente falla.

### Fase 2: Análisis de Patrones
Agrupa la evidencia. Compara lo que tienes contra la línea base de cómo debería funcionar. 

### Fase 3: Hipótesis
Formula una teoría clara basada EXCLUSIVAMENTE en la evidencia de la Fase 1 y 2. Sin adivinanzas en la oscuridad.

### Fase 4: Implementación
Aplica el parche preciso abordando la causa raíz.

**Red Flags (Detente inmediatamente):** 
Si cambias un archivo y ves un nuevo error no relacionado, revierte el cambio. Si el proceso iterativo revela "no hay causa raíz explícita", asume que tus logs no tienen suficiente verbosidad. Vuelve a la Fase 1.
