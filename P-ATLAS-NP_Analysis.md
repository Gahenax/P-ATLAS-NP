# Análisis del Dataset P-ATLAS-NP (Campaña NPX-PROD-0.1)

El repositorio `P-ATLAS-NP` contiene los resultados de una cacería de vectores (Vector Hunt) sobre la frontera de transiciones de fase (dureza computacional).

## 1. Composición de los Datasets (`/evidence`)

El orquestador generó una suite completa de telemetría y métricas estructurales:

- **`atlas.csv` (Base de Datos Principal):** 
  - Contiene información probabilística de instancias SAT, identificadores, variables (`n_vars`), relación cláusula/variable (`ratio`), y coordenadas espectrales (e.g., `lambda2`, `spectral_entropy`).
  - Mapea la **dureza algorítmica** (`target_H`) y el **desplazamiento estructural** (`target_D`).
  - Clasifica qué instancias caen en la "Frontera" (aquellas con alta variabilidad local de dureza) a través de los campos `frontier_flag` y `local_std_H_knn`.

- **`vector.json` (Vector Comprimido):**
  - Almacena un espacio latente de 7 dimensiones proyectado de las características.
  - Dimensiones: `lambda2`, `ratio`, `spectral_entropy`, `spectral_gap`, `largest_component_frac`, `degree_skew`, `degree_mean`.
  - Estabilidad proyectada: ~`0.905`.

- **`report.md` & `obstructions.jsonl` (Auditoría de Gates):**
  - Muestra que el vector final fue **RECHAZADO (VECTOR_REJECTED)**.
  - Pasó pruebas de invariancia de permutación y generadores.
  - **Pruebas Fallidas:** Semántica (la distribución normalizada era anómala con una puntuación de `0.0065`) y Perturbación (el vector colapsó al perturbar un 2% los grafos de las instancias, arrojando un $\Delta v$ de `1.8356`).

- **`frontier.json` (Frontera de Poincaré):**
  - Determina que la frontera de caos estructural agrupa al **20% de la población** de grafos.

## Opciones de Análisis Profundo

Ya que tenemos los datos procesados, podemos tomar varias direcciones analíticas:

1. **Análisis Visual (Plotting):** Crear un script Python que dibuje el diagrama de dispersión del Atlas (`lambda2` vs `spectral_entropy`) coloreando los puntos según su dureza empírica (`target_H`) y la `frontier_flag` para "ver" la transición de fase.
2. **Corrección del Vector (Engineering):** Analizar por qué falló el "Gate 5" de perturbación e intentar entrenar un extractor más robusto.
3. **Mapeo Cruzado:** Intentar extrapolar si el fenómeno de variabilidad local (`local_std_H`) de P-ATLAS tiene un eco con la rigidez estructural de los ceros de Riemann que estábamos minando.
