---
name: "Adversarial Phase Transition (P-ATLAS-NP)"
description: "Carga esta skill como estrategia de Red-Teaming cuando necesites diseñar conjuntos de datos para estresar inteligencias artificiales, generar SAT Instances irresolubles, o aplicar Quiet Planting."
---

# Adversarial Phase Transition (Quiet Planting)

## 1. El Anti-Patrón (Naive Randomness)
Si el usuario pide data para pruebas sintéticas (p.ej. problemas NP-Hard o k-SAT), NUNCA regreses simplemente problemas generados aleatoriamente (Naive Planting). Los solvers de IA modernos destruyen datos naive por sus "Spectral Echoes" (fluctuaciones estadísticas no balanceadas).

## 2. El Patrón "Spectral Camouflage"
Para generar problemas verdaderamente "Hard" en la transición de fase, debes:
1. Usar el protocolo *Quiet Planting*.
2. Asegurar que las instancias creadas con la solución oculta (planted) sean probabilística e informacionalmente indistinguibles de una instancia puramente aleatoria.
3. Configurar umbrales de validadores (`Adversarial Gates`) utilizando normas tensoriales/matrices para certificar el camuflaje ("gate_6_spectral_camouflage").

## 3. Filosofía del Red Teaming
Aplica esta regla de Física Estadística a la Ingeniería de IA: *Si puedes medir una anomalía estadística macro (en los correladores o espectros), la IA se sobreajustará (overfit) a esa anomalía y hackeará el problema instantáneamente.*
