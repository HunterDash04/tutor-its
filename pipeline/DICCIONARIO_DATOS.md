# Diccionario de datos

Este documento describe todas las fuentes de datos, las variables derivadas y las tablas de la aplicación.
Los rangos corresponden a los datasets generados el 3 de octubre de 2026.

---

## 1. Fuentes de datos

| Fuente | Uso en el sistema | Unidad | Volumen | Acceso y licencia |
|---|---|---|---|---|
| **OULAD**, Open University Learning Analytics Dataset (Kuzilek, Hlosta y Zdrahal, 2017) | Modelo A: diagnóstico del estado cognitivo | Estudiante-curso | 32,593 matrículas; 7 módulos; 22 presentaciones (2013–2014) | Público, CC BY 4.0. Se usan `studentInfo`, `studentRegistration`, `courses`, `assessments`, `studentAssessment`, `vle` y `studentVle` (este último agregado por día en `vle_features_agregadas.csv`). |
| **Codeforces**, API pública oficial | Recomendador híbrido, catálogo de ejercicios y calibración del diagnóstico en vivo | Primer intento de un usuario en un problema | 1,500 usuarios con rating de 800 a 1599; 504,728 envíos; 250,394 primeros intentos; 11,425 problemas | Datos públicos descargados con `descargar_codeforces.py`. Los identificadores de usuario se reemplazan por un hash irreversible. |

---

## 2. Dataset del Modelo A: `dataset_estudiante_corte50.csv`

Generado por `construir_dataset_estudiante.py 0.5`.
- **Unidad:** una fila por estudiante-curso (24,601 filas).
- **Información usada:** solo lo observado hasta el **50% de la duración del curso**.
- **Excluidos:** los estudiantes que se retiraron antes de ese corte.

### Identificadores (no se usan como variables predictoras)
| Variable | Tipo | Descripción |
|---|---|---|
| `id_student` | entero | Identificador anónimo del estudiante en OULAD. Se usa para agrupar la validación, de modo que un estudiante nunca esté en entrenamiento y prueba a la vez. |
| `code_module` | categórica (7) | Módulo o curso (AAA–GGG). Se usa como variable predictora codificada en one-hot. |
| `code_presentation` | categórica | Presentación del curso (p. ej. 2013J). Se usa para la validación temporal (2013 → 2014). |

### Variable objetivo
| Variable | Valores | Descripción |
|---|---|---|
| `resultado_final` | Pass, Fail, Withdrawn, Distinction | Resultado oficial del curso en OULAD. |

| Estado del sistema | Resultado en OULAD | Proporción |
|---|---|---|
| Riesgo - Reforzar Fundamentos | Fail + Withdrawn | 37.5% |
| Aprendizaje Normal - Mantener Ruta | Pass | 50.2% |
| Dominio Alto - Ruta Avanzada | Distinction | 12.3% |

### Variables predictoras (26)

| Variable | Grupo | Tipo | Rango | % nulos | Definición |
|---|---|---|---|---|---|
| `nivel_educativo` | Perfil | ordinal | 0–4 | 0 | Máximo nivel educativo previo: 0 = sin estudios formales … 4 = posgrado. |
| `banda_edad` | Perfil | ordinal | 0–2 | 0 | 0 = 0–35 años; 1 = 35–55; 2 = 55 o más. |
| `indice_privacion_imd` | Perfil | ordinal | 0–9 | 3.8 | Decil del índice de privación socioeconómica de la zona de residencia (0 = más privado). |
| `discapacidad` | Perfil | binaria | 0–1 | 0 | Declaró discapacidad. |
| `intentos_previos` | Perfil | entero | 0–6 | 0 | Veces que cursó antes el mismo módulo. |
| `creditos_matriculados` | Perfil | entero | 30–630 | 0 | Créditos en los que está matriculado. |
| `dias_registro_antes_inicio` | Perfil | entero | −167–311 | 0 | Días de anticipación con que se inscribió (negativo = se inscribió después del inicio). |
| `semestre_febrero` | Perfil | binaria | 0–1 | 0 | La presentación empieza en febrero (B) y no en octubre (J). |
| `clics_totales` | Actividad en la plataforma | entero | 0–14,572 | 0 | Clics en el entorno virtual hasta el día de corte. |
| `dias_activos` | Actividad en la plataforma | entero | 0–157 | 0 | Días distintos con actividad. |
| `clics_antes_inicio` | Actividad en la plataforma | entero | 0–3,731 | 0 | Clics antes del primer día del curso. |
| `clics_ultimas_2_semanas` | Actividad en la plataforma | entero | 0–5,092 | 0 | Clics en los 14 días previos al corte. |
| `semanas_activas` | Actividad en la plataforma | entero | 0–24 | 0 | Semanas distintas con actividad. |
| `tendencia_clics` | Actividad en la plataforma | real | 0–574 | 0 | (clics de la 2.ª mitad + 1) / (clics de la 1.ª mitad + 1) de la ventana observada. |
| `dias_desde_ultima_actividad` | Actividad en la plataforma | entero | 0–164 | 0 | Días entre la última actividad y el corte. |
| `clics_por_dia_activo` | Actividad en la plataforma | real | 0–158 | 0 | `clics_totales` / `dias_activos`. |
| `evaluaciones_vencidas` | Evaluaciones | entero | 2–8 | 0 | Evaluaciones (sin el examen final) con fecha límite anterior al corte. |
| `evaluaciones_entregadas` | Evaluaciones | entero | 0–8 | 0 | De esas, cuántas entregó antes del corte. |
| `tasa_entrega` | Evaluaciones | real | 0–1 | 0 | Entregadas / vencidas. |
| `nota_promedio` | Evaluaciones | real | 0–100 | 0 | Nota media de las evaluaciones vencidas (las no entregadas cuentan como 0). |
| `nota_minima` | Evaluaciones | real | 0–100 | 0 | Nota mínima entre las vencidas. |
| `nota_ultima_evaluacion` | Evaluaciones | real | 0–100 | 6.3 | Nota de la última evaluación entregada. |
| `entregas_tardias` | Evaluaciones | entero | 0–8 | 0 | Entregas posteriores a la fecha límite. |
| `retraso_promedio_dias` | Evaluaciones | real | 0–69 | 6.3 | Días de retraso promedio (0 si entregó a tiempo). |
| `evaluaciones_reprobadas` | Evaluaciones | entero | 0–8 | 0 | Evaluaciones vencidas con nota menor a 40. |
| `nota_ponderada_relativa` | Evaluaciones | real | 0–100 | 9.5 | Promedio de notas ponderado por el peso oficial de cada evaluación. |

**Tratamiento de nulos.** Se imputan con la mediana dentro del pipeline de entrenamiento, ajustada solo con los datos de entrenamiento. Los nulos aparecen cuando el estudiante no entregó ninguna evaluación o cuando todas tienen peso 0.

---

## 3. Datos de Codeforces

### 3.1 `problemas_codeforces.csv` (catálogo)
| Columna | Descripción |
|---|---|
| `id_problema` | Concurso + índice (p. ej. `1780B`). |
| `contest_id`, `indice` | Componentes del identificador. |
| `nombre` | Título del problema. |
| `rating` | Dificultad oficial (800–3500). |
| `etiquetas` | Temas oficiales separados por `;`. |
| `veces_resuelto` | Número de usuarios que lo resolvieron. |

### 3.2 `envios_codeforces.csv` (envíos)
| Columna | Descripción |
|---|---|
| `id_usuario` | Hash anónimo del usuario (`u_` + 12 caracteres). |
| `rating_usuario` | Rating del usuario el día de la descarga. Solo se usó para seleccionar la muestra (800–1599); no es variable predictora. |
| `id_envio` | Identificador del envío. |
| `id_problema`, `rating_problema`, `etiquetas` | Problema al que corresponde el envío. |
| `veredicto` | Resultado del juez (`OK`, `WRONG_ANSWER`, etc.). Se descartan `COMPILATION_ERROR`, `SKIPPED`, `TESTING` y `REJECTED`. |
| `tests_superados` | Casos de prueba superados. |
| `tiempo_unix` | Fecha y hora del envío. |
| `lenguaje`, `tipo_participante` | Lenguaje usado; si el envío fue en concurso, práctica o virtual. |

**Unidad de análisis.** El **primer intento** de cada usuario en cada problema.
**Variable objetivo.** `exito` = 1 si ese primer envío fue aceptado.
**Proporción de éxito al primer envío:** 60.8%.

### 3.3 Categorías temáticas (`topicos_codeforces.py`)
Las 36 etiquetas oficiales se agrupan en 11 categorías. Un problema puede pertenecer a varias.

| Categoría | Etiquetas de Codeforces |
|---|---|
| Implementación y Simulación | implementation, brute force, interactive, schedules |
| Algoritmos Voraces | greedy, constructive algorithms |
| Matemáticas y Teoría de Números | math, number theory, combinatorics, probabilities, matrices, chinese remainder theorem, fft |
| Programación Dinámica | dp, divide and conquer |
| Estructuras de Datos | data structures, dsu, hashing |
| Ordenamiento y Búsqueda | sortings, binary search, two pointers, ternary search, meet-in-the-middle |
| Grafos | graphs, dfs and similar, shortest paths, flows, graph matchings, 2-sat |
| Árboles | trees |
| Cadenas de Texto | strings, string suffix structures, expression parsing |
| Manipulación de Bits | bitmasks |
| Geometría y Juegos | geometry, games |

### 3.4 Variables del recomendador (17, `motor_recomendacion.py`)
Todas se calculan **solo con el historial previo** al intento. Son las mismas en el entrenamiento y en la aplicación.

| Variable | Fuente | Rango observado | Definición |
|---|---|---|---|
| `rating_problema` | Contenido | 800–3500 | Dificultad oficial del problema. |
| `rating_conocido` | Contenido | 0–1 | El problema tiene dificultad oficial. |
| `n_categorias` | Contenido | 1–9 | Número de categorías del problema. |
| `habilidad_elo` | Estado del estudiante | 654–2024 | Habilidad estimada tipo Elo (inicio 1000). |
| `brecha_dificultad` | Estado del estudiante | −1223–2748 | `rating_problema` − `habilidad_elo`. |
| `prob_elo` | Estado del estudiante | 0–1 | Probabilidad de éxito según Elo, ajustada por categoría. |
| `ajuste_categoria` | Estado del estudiante | −189–292 | Ajuste de habilidad acumulado en las categorías del problema. |
| `intentos_previos_log` | Estado del estudiante | 0–6.6 | log(1 + problemas intentados). |
| `tasa_exito_global` | Estado del estudiante | 0.15–0.94 | Tasa de éxito al primer envío (suavizada). |
| `exito_ultimos_5` | Estado del estudiante | 0–1 | Éxito en los últimos 5 intentos. |
| `exitos_categoria`, `fallos_categoria` | Estado del estudiante (PFA) | 0–984 / 0–474 | Éxitos y fallos previos en las categorías del problema. |
| `tasa_exito_categoria`, `tasa_exito_categoria_min` | Estado del estudiante | 0.12–0.94 | Tasa suavizada media y mínima en esas categorías. |
| `dificultad_colectiva` | Colaborativo | 0.03–0.97 | Tasa de éxito al primer envío de **otros** usuarios en ese problema (suavizada). |
| `intentos_colectivos_log` | Colaborativo | 0–6.5 | log(1 + intentos de otros usuarios en el problema). |
| `dominio_svd_categoria` | Colaborativo | 0.19–0.91 | Dominio estimado en las categorías del problema, proyectando al estudiante en los factores SVD de la matriz usuario × categoría. |

### 3.5 Calibración del diagnóstico en vivo (`calibracion_diagnostico.json`)
| Campo | Valor | Descripción |
|---|---|---|
| `alfa` | 0.2 | Peso de la media móvil exponencial. |
| `umbral_riesgo` | −0.0481 | Por debajo de este valor del índice, el estado es Riesgo. |
| `umbral_dominio` | 0.1734 | Por encima de este valor del índice, el estado es Dominio Alto. |
| `prevalencia_objetivo` | 0.375 / 0.502 / 0.123 | Proporción de estados en OULAD usada para fijar los umbrales. |
| `razon_verosimilitud`, `p_valor` | 18.0; 2.2×10⁻⁵ | Información que aporta el índice para predecir el siguiente intento, adicional a la probabilidad del modelo. |

**Índice de rendimiento:** I₀ = 0; Iₜ = α·(éxitoₜ − P(éxito)ₜ) + (1 − α)·Iₜ₋₁.

---

## 4. Base de datos de la aplicación (PostgreSQL en Neon / SQLite local)

| Tabla | Columnas principales | Descripción |
|---|---|---|
| `usuarios` | id, usuario, nombre, hash, rol, gpa, habilidad_inicial, handle_cf, creado_en, ultimo_acceso | Cuentas. `hash` = PBKDF2-SHA256 con sal; la contraseña nunca se guarda. `rol` = estudiante o docente. |
| `intentos` | id, usuario_id, id_problema, nombre_problema, rating, etiquetas, categoria_objetivo, estado_previo, p_exito, meta, mostrado_en, registrado_en, resultado, envios, tiempo_s, modo, estado_resultante, habilidad_despues | Cada ejercicio recomendado y su resultado. `resultado` = resuelto, no_resuelto u omitido. `modo` = manual o codeforces. `tiempo_s` se mide automáticamente desde `mostrado_en`. Si `registrado_en` es nulo, la recomendación sigue pendiente. |
| `consentimientos` | id, usuario_id, version_aviso, aceptado_en | Evidencia de aceptación del aviso de privacidad (Ley N.° 29733). |

Las fechas se guardan en segundos Unix (UTC).

---

## Referencia
Kuzilek, J., Hlosta, M., & Zdrahal, Z. (2017). Open University Learning Analytics dataset. *Scientific Data, 4*, 170171. https://doi.org/10.1038/sdata.2017.171
