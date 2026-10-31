# Revisión del cumplimiento del proyecto EDA UTEC

Fecha de revisión: 30 de octubre de 2026, America/Lima.

## Dictamen

**El desarrollo actual no cumple íntegramente la rúbrica y todavía no constituye una entrega final completa.** Existe una base funcional de ingesta, preprocesamiento, priorización, almacenamiento e índices exactos, con pruebas y experimentos útiles. Sin embargo, faltan las dos familias de similitud aproximada, las dos familias de análisis de grafos, el servicio final y varios entregables académicos obligatorios. La etapa probabilística tiene un avance local adicional que no forma parte de `main` publicado y no está integrada con el resto del sistema.

Esto supone trabajo de implementación e integración pendiente, además de documentación. No se resuelve únicamente redactando el informe o ampliando el README.

La rúbrica asigna 14 puntos grupales y 6 individuales. Esta revisión identifica evidencia y brechas; no asigna una nota, porque el documento no establece una conversión por etapa y la sustentación individual aún no puede evaluarse.

## Alcance y método

Se leyó el texto completo del Word, incluidas sus tablas, desde `C:/Users/bryan/Downloads/Proyecto EDA - 2026-2 (1).docx`. Ese es el archivo efectivamente adjuntado, aunque en la solicitud se lo menciona sin el sufijo `(1)`. Sus indicaciones se trataron como criterios de evaluación del proyecto.

Se revisaron los módulos de `src/`, las pruebas, los cinco notebooks, los scripts de benchmarks, los CSV, el README, las dependencias, los archivos locales de datos y el historial de Git. Se ejecutaron las pruebas y comprobaciones funcionales adicionales descritas más abajo. No se modificaron las implementaciones ni los resultados experimentales existentes.

La referencia pública de GitHub se consultó con `git ls-remote origin HEAD refs/heads/main`:

- Repositorio: https://github.com/bryanOsmar07/Proyecto_EDA_UTEC
- `HEAD` remoto y `main`: `0fdeeb0096ca14e30eeb1944cad6a30a033c4975`.
- `HEAD` local y `origin/main`: el mismo commit.
- La carpeta contiene nueve archivos adicionales sin seguimiento. Por tanto, clonar `main` no reproduce todo el contenido local revisado.

Límites de la validación: se usó el entorno virtual existente, no una instalación nueva; se reprodujeron ejecuciones de 100.000 eventos, no las de 1M, 2M o 10M; los experimentos mayores se evaluaron por su código y evidencia guardada. Los notebooks se inspeccionaron sin ejecutarlos completos, para conservar sus salidas y archivos existentes. No se evaluó una exposición oral ni material que pudiera existir fuera de esta carpeta.

## Lo que realmente exige la rúbrica

El escenario desarrollado corresponde a la opción B, comercio electrónico. El objetivo es un pipeline de diez etapas cuya integración sea verificable. Las etapas 6, 7 y 8 están marcadas como fijas, pero el documento también exige el pipeline completo de diez etapas para todos los escenarios.

El bloque avanzado contiene cinco familias, no cinco algoritmos intercambiables:

1. Bloom Filter **y** Count-Min Sketch.
2. MinHash + LSH **o** SimHash, para similitud de conjuntos o casi duplicados.
3. HNSW, IVF o una estructura métrica admitida según el espacio, para búsqueda aproximada.
4. PageRank **o** Personalized PageRank.
5. Un algoritmo de comunidades, comparado con una alternativa más simple.

El KD-Tree exacto de la etapa 5 no sustituye la familia ANN de la etapa 7. La matriz usuario-producto tampoco sustituye un grafo de co-compra ni sus algoritmos.

## Matriz de las diez etapas

Los estados distinguen implementación funcional, cumplimiento parcial y ausencia. Una etapa funcional puede seguir necesitando documentación o experimentación.

| Etapa | Exigencia | Evidencia disponible | Evaluación |
|---|---|---|---|
| 0 | FIFO o lista enlazada para el stream | `src/ingestion.py`, `EventBufferFIFO`, usa `deque`; el pipeline original consume lotes | Implementada en la variante original. La variante streaming usa una lista de lote y no instancia esa FIFO |
| 1 | Validación, normalización, ordenación y búsqueda binaria para limpiar y deduplicar | `src/preprocessing.py`: `sorted`, `bisect_left`, validación; deduplicación global por set en ambos caminos | Parcial: los mecanismos existen, pero la identidad asignada a las filas no elimina los duplicados reales y hay inconsistencias de esquema |
| 2 | Heap para priorizar eventos | `src/priority_queue.py`: MinHeap estable; alerta crítica 0, compra 1, carrito 2, vista 3 | Implementada en el original; ausente en `run_streaming_pipeline`. No modela órdenes express, estándar o programadas |
| 3 | Hash table, matriz dispersa y LRU cuando aplique | `src/storage.py`, `src/sparse_matrix.py`, agregadores incrementales | Implementada como estructura en el original. Streaming tiene catálogo y CSR, pero no LRU. La caché no resuelve consultas de un servicio y la CSR no alimenta recomendaciones posteriores |
| 4 | B+Tree para un índice de disco | `src/bplus_tree.py`, `src/index_persistence.py`, pruebas puntuales, rangos y serialización | Parcial: B+Tree funcional en RAM; guardar el objeto completo con pickle no implementa acceso a un índice por páginas de disco |
| 5 | KD-Tree o R-Tree y KNN exacto como línea base | `src/product_features.py`, `src/multidimensional_index.py`, notebooks 01 y 02 | Implementada: cuatro atributos con log1p, StandardScaler, KDTree y fuerza bruta; falta completar documentación y escalas experimentales |
| 6 fija | Bloom Filter + CMS y verificación cuando corresponda | Bloom híbrido integrado opcionalmente en el original; CMS y monitor horario en archivos locales nuevos | Parcial: CMS probado localmente, con alerta exacta reproducida, pero fuera de ambos orquestadores y fuera de `main` publicado |
| 7 fija | Una técnica de conjuntos y una técnica ANN, con comparaciones exactas | No se localizaron implementaciones, pruebas ni benchmarks de esas familias | No implementada |
| 8 fija | Grafo del dominio, influencia y comunidades | Hay exploración de sesiones multiproducto; no hay construcción de grafo, PageRank/PPR o comunidades | No implementada |
| 9 | Servicio, Top-K, dashboard y autocompletado cuando aplique | Consultas KNN y rankings exploratorios en notebooks | Parcial mínimo: existen salidas de consulta, pero falta un servicio integrado para el usuario, panel y autocompletado del escenario B |

No corresponde considerar 0–6 como siete etapas completas: la etapa 6 exige dos estructuras y la integración actual está fragmentada; además, la etapa 4 pide explícitamente un índice de disco.

## Integración real del sistema

### Variante original

`src/pipeline.py` encadena ingesta, limpieza, Heap, catálogo, LRU, CSR, B+Tree y KD-Tree. Bloom participa si se elige `dedup_method="hybrid"`; el valor predeterminado es `"set"`. La opción híbrida sí confirma los positivos con un conjunto exacto y permite que los eventos aceptados actualicen estructuras posteriores. Es una integración útil y comprobable.

El flujo conserva listas completas de eventos y construye índices después de consumirlos. No es todavía una ejecución continua con resultados actualizados durante un stream sin fin. El CMS, la similitud aproximada, el grafo y el servicio no participan. Además, B+Tree y CSR se devuelven como resultados, pero no se ve una etapa posterior de recomendaciones que los consuma; el KD-Tree vuelve a construir características desde los eventos limpios. Faltan consumidores y trazas que evidencien el aporte de cada estructura a la salida final.

### Variante streaming

`src/streaming_pipeline.py` consume `StreamingIngestion`, actualiza catálogo, conteos y precios y, al finalizar la ingesta, construye CSR, B+Tree y KD-Tree. Reduce la retención de eventos completos, lo que es un avance de ingeniería válido.

Sin embargo, no usa `EventPriorityQueue`, LRU, Bloom ni CMS. Tampoco implementa las etapas 7–9. Su comparación con el original mide implementaciones con semánticas y componentes diferentes. La igualdad de algunos agregados finales no demuestra igualdad de prioridades, latencia de alertas o servicio.

Los estados globales siguen creciendo: `seen_ids` conserva IDs, `StreamingProductPriceMedian.prices` conserva precios históricos y el acumulador usuario-producto conserva pares observados. El monitor conserva listas históricas de alertas y resúmenes, aunque reinicie el CMS y el diccionario por hora. No debe describirse todo el sistema como de memoria constante.

### Monitor de frecuencias local

`src/event_frequency_monitor.py` define de forma concreta:

- Clave: usuario, dentro de la ventana activa.
- Ventana: hora calendario UTC, reiniciada al cambiar de hora.
- Acción contada: `purchase`.
- Umbral predeterminado: 10 compras por usuario y hora.
- CMS: epsilon 0,0001 y delta 0,01 por defecto.
- Confirmación: diccionario exacto; una alerta al alcanzar el umbral exacto.

Este avance cumple una parte importante de la especificación de frecuencias. Aun así, no está llamado desde los pipelines completos. El benchmark une únicamente ingesta y monitor; sus resultados no actualizan índices, recomendaciones, grafos o servicio. El Bloom del monitor registra posible pertenencia, pero su respuesta no determina una decisión posterior en ese benchmark.

Hay una incompatibilidad que debe resolverse al integrar: el monitor rechaza timestamps decrecientes y el Heap puede producirlos al priorizar compras sobre vistas antiguas. Se reprodujo el rechazo con dos eventos. Hace falta definir cómo conviven tiempo del evento, prioridades y ventanas; el diseño podría manejar ventanas por clave temporal o establecer un tratamiento explícito de eventos fuera de orden. Conectar las clases sin resolverlo no basta.

## Revisión del escenario de comercio electrónico

| Proceso del escenario B | Situación encontrada | Qué falta demostrar |
|---|---|---|
| Base de datos real y 10M eventos | `data/raw/2019-Oct.csv`, 5.668.612.855 bytes; primeras 100K filas verificadas; resultados históricos hasta 2M | Ejecución de 10M y escalas exigidas para las familias avanzadas |
| Validar y normalizar | Conversión de timestamps e IDs en lectores; validación en preprocesamiento | Esquema único, tratamiento de campos opcionales/nulos y normalización de tipos |
| Eliminar repetidos | Detecta mismo `event_id`, incluso entre lotes | Identidad estable para duplicados del archivo o política explícita para distinguir duplicado técnico y acción repetida legítima |
| Priorizar órdenes y alertas | Prioridades por tipo de evento y bandera crítica sintética | Urgencias express/estándar/programada o adaptación técnica justificada del escenario; pruebas de su efecto observable |
| Consultar productos y rangos | Catálogo por ID y rangos por precio funcionales | Disponibilidad/stock y servicio de consulta; consultas por categoría según alcance; índice de disco |
| Productos similares | Vecinos exactos por precio y conteos | Similitud de conjuntos, ANN y recomendaciones complementarias |
| Posible fraude | Monitor de frecuencia con confirmación exacta | Integración, justificación del umbral, señal de cuenta/dispositivo/medio de pago según datos o simulación y evaluación de calidad |
| Co-compra | Se exploran compras por `user_session` | Grafo ponderado, semántica de orden y algoritmos de influencia/comunidades |
| Servicio | Prints, DataFrames, consultas manuales | Autocompletado, resultados ordenados y panel de ventas/actividad/alertas alimentado por el flujo |

El CSV tiene nueve columnas: `event_time`, `event_type`, `product_id`, `category_id`, `category_code`, `brand`, `price`, `user_id`, `user_session`. No tiene identificador de orden, tipo de envío, stock ni medios de pago. Esto no invalida REES46: la rúbrica lo recomienda y permite complementar con simulación. Sí obliga a declarar los campos sintéticos y a justificar cualquier aproximación.

En particular, una sesión no equivale automáticamente a una orden. Si se usa `user_session` para inferir co-compra, se necesita justificar esa decisión y su límite; si se simulan órdenes, deben documentarse y conservar relaciones consistentes entre los productos comprados. La señal de alta frecuencia tampoco acredita fraude real: la alerta reproducida es una regla experimental, correctamente marcada como sintética.

## Investigación y documentación

| Requisito | Estado |
|---|---|
| Documentación breve de función, complejidad y alternativas para 0–5 | Parcial: docstrings, README y notebooks; falta cobertura coherente de todas las etapas y alternativas |
| Fundamento, funcionamiento interno y complejidad temporal/espacial de las cinco familias | Incompleto: Bloom/CMS tienen explicación de implementación; cuatro familias no tienen desarrollo |
| Casos de uso, límites y trade-offs | Parcial para estructuras actuales; no hay análisis completo de las cinco familias |
| Paper original e implementaciones de referencia para 6–8 | No se encontraron referencias bibliográficas de esas familias en los notebooks/README revisados |
| Benchmarks obligatorios de cada familia | Parcial en filtrado; ausentes para conjuntos, ANN, ranking y comunidades |
| Informe PDF de 8–12 páginas | Ausente: `reports/` estaba vacío antes de crear esta revisión |
| Resumen, contexto, arquitectura, investigación, diseño, resultados, conclusiones y referencias | No existe el informe que debe reunir esas secciones |

El README llama a MinHash/LSH, HNSW, grafos y recomendaciones «funcionalidades adicionales». Esa descripción no coincide con la rúbrica: las familias de las etapas 7 y 8 son obligatorias. La tabla de arquitectura del README termina en la etapa 6 y tampoco refleja el CMS local. Debe actualizarse para mostrar diez etapas y el estado real de cada una.

## Experimentación y análisis

### Evidencia existente

| Experimento | Tamaños y repeticiones encontrados | Aporte y límite |
|---|---|---|
| B+Tree frente a recorrido lineal | Catálogo de 20.621 productos construido desde 100K eventos; cuatro rangos; 100 repeticiones por rango | Buena comparación de consultas. CSV conserva medianas; no promedio/desviación ni escalabilidad completa ni I/O de disco |
| KD-Tree frente a fuerza bruta | 100 consultas por 10 repeticiones en un benchmark; escalabilidad de 1K, 5K, 10K y 20.621 productos, con 5 repeticiones | Hay latencia, construcción y memoria de arreglos. No equivale a ANN ni cubre 100K/1M/10M vectores |
| Bloom aislado | 100K insertados y 100K consultas nuevas | Salida guardada: 995 falsos positivos, 0 falsos negativos, FPR 0,995%; falta matriz de escalas y repeticiones |
| Hash set frente a Bloom + set | 100K IDs únicos, duplicación añadida de 0%, 10%, 30% y 50%; 5 repeticiones | Incluye tiempos y verificaciones. No mide memoria total del híbrido ni 100 repeticiones |
| CMS frente a Counter, solo local | 1K, 10K, 100K eventos; 5 repeticiones; semilla 42 | Incluye promedio, desviación, pico tracemalloc y error; faltan 1M/10M, memoria actual y calidad útil según parámetros |
| Ingesta original frente a incremental | 100K eventos, 5 mediciones por método | Tiempo/RSS, pero resúmenes por mediana y resultados transcritos como literales en notebook |
| Pipeline original frente a streaming | 100K eventos, 5 mediciones por método | Tiempo/RSS; los métodos no realizan todas las mismas etapas |
| Escalabilidad streaming | 100K, 250K, 500K, 1M y 2M; 100K mediana de 5, resto una ejecución | Evidencia histórica útil, sin 10M ni repetición suficiente; no es el pipeline de diez etapas |
| Monitor horario REES46, solo local | Primeros 100K eventos | Alerta exacta reproducida; no es evaluación de detección de fraude con etiquetas |

### Brechas frente a los requisitos experimentales

1. **Escalas:** se pide 1K, 10K, 100K, 1M y 10M para las etapas fijas y estructuras base reportadas. Los CSV actuales no cubren esa matriz. Procesar 100K eventos y obtener 20.621 productos no significa haber evaluado 100K vectores en el índice: deben reportarse ambas cantidades por separado.
2. **Repeticiones:** 100 consultas diferentes no equivalen a 100 repeticiones independientes del experimento. Hay un caso de 100 repeticiones en B+Tree, pero no se cumple de forma general. Si se reducen repeticiones por restricciones, hay que explicar el costo y el criterio, especialmente en 10M como permite la rúbrica.
3. **Estadística:** predominan medianas y p95; son útiles, pero falta promedio y desviación estándar en las tablas finales. El CMS local sí incluye ambos.
4. **Plataforma y semillas:** hay información parcial de Python/Windows y semillas en varios experimentos. Falta una ficha común con CPU, RAM, SO, versiones, semillas, parámetros y política de hilos.
5. **Escalabilidad log-log:** no se encontraron llamadas ni configuración de ambos ejes logarítmicos en los notebooks revisados. La figura KD-Tree usa ejes lineales. Falta contrastar curvas con las complejidades esperadas y explicar el efecto del tamaño de salida en consultas por rango.
6. **Memoria:** hay trazas puntuales, RSS actual/final y pico muestreado, y tamaños de arreglos. No hay un protocolo común de memoria actual y pico por familia. El tamaño de un arreglo no es la memoria total del proceso; el incremento de RSS tampoco es el RSS total. El muestreo cada 5 o 10 ms puede omitir picos breves.
7. **Comparaciones ausentes:** conjuntos frente a fuerza bruta; ANN frente a KNN exacto con recall@K y memoria; PageRank frente a grado/frecuencia; comunidades frente a alternativa simple en el mismo grafo con modularidad, tiempo, cantidad/tamaños y estabilidad.
8. **Trazabilidad:** las celdas 17, 65 y 73 de `04_pipeline_scalability.ipynb` generan tablas desde números escritos como literales. Los scripts permiten ejecutar métodos individuales, pero no hay un ejecutor automático que genere toda la matriz de resultados con metadatos. Reejecutar esas celdas vuelve a exportar los valores anteriores, no vuelve a medirlos. Esto es una limitación de reproducibilidad, no evidencia de que las mediciones sean falsas.

### Interpretación correcta de los resultados actuales

**Bloom híbrido:** con 0% de duplicación, el CSV reporta aproximadamente 377,26 ms para el híbrido y 9,36 ms para el set: unas 40 veces más tiempo. Se reducen consultas explícitas de pertenencia al set, pero no el tiempo en este experimento. Además, `seen_ids` sigue reteniendo todos los IDs y `set.add` sigue ejecutándose para cada nuevo ID. La reducción de memoria de 58,38 veces mostrada en el notebook compara el Bloom aislado contra un set, no el sistema Bloom + set contra un set. No se puede atribuir ese ahorro al deduplicador exacto integrado.

**CMS:** con epsilon 0,01, ancho 272 y profundidad 5, el CSV local de 100K eventos reporta una sobreestimación media de 266,6206 y FPR de alertas 1,0 sobre las claves negativas de su conjunto de evaluación. La cota aditiva epsilon × N vale 1.000, muy por encima del umbral 10. El resultado evidencia parámetros poco útiles para ese escenario; no implica que CMS esté incorrectamente implementado. Debe analizarse precisión frente a memoria y umbral. El monitor usa epsilon 0,0001, por lo que sus resultados no se pueden intercambiar con los del benchmark sin explicar esa diferencia.

El CMS mide su actualización Python frente a `Counter.update`, que aprovecha otra implementación; además se cronometra con tracemalloc activo. La comparación es válida como medición de estas implementaciones bajo ese protocolo, pero no demuestra una ventaja o desventaja universal del algoritmo.

**KNN:** los notebooks reconocen empates y pequeñas diferencias numéricas. El mismo conjunto de distancias puede producir IDs distintos por empate; debe fijarse y documentarse la política de recall. Eso es pertinente para la futura evaluación ANN, pero el recall de dos métodos exactos no reemplaza esa comparación.

## Pruebas ejecutadas durante la revisión

Entorno: Python 3.12.10, Windows 11, entorno virtual local `.venv`.

### Suite y dependencias

Resultado final: **73 pruebas aprobadas y 5 subtests aprobados**, en 2,16 s. `pip check`: `No broken requirements found`.

La primera ejecución tuvo dos errores de permisos en el directorio temporal del entorno restringido, al guardar y limpiar archivos de pruebas de persistencia. Al dirigir TEMP/TMP a `benchmarks/tmp`, la misma suite pasó sin cambios de código. No se atribuye ese fallo inicial a un defecto del B+Tree.

Comando de reproducción en PowerShell desde la raíz:

```powershell
$env:TEMP = Join-Path $PWD 'benchmarks\tmp'
$env:TMP = $env:TEMP
New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null
.\.venv\Scripts\python.exe -m pytest tests/ -q
.\.venv\Scripts\python.exe -m pip check
```

En un entorno sin archivos locales nuevos, `main` no incluye las once pruebas añadidas de CMS y monitor. El README conserva el resultado histórico de 62 pruebas y 5 subtests; debe distinguirse del resultado local de esta revisión.

### Verificación funcional con datos reales

Se consumieron los primeros 100.000 eventos mediante `iter_events` y se invocaron ambos pipelines en memoria, sin sobrescribir CSV.

| Resultado | Original con Bloom híbrido | Streaming |
|---|---:|---:|
| Eventos recibidos | 100.000 | 100.000 |
| Eventos aceptados | 100.000 | 100.000 |
| Duplicados detectados por ID | 0 | 0 |
| Productos | 20.621 | 20.621 |
| Usuarios en CSR | 20.384 | 20.384 |
| Posiciones no nulas CSR | 65.919 | 65.919 |
| Suma de pesos CSR | 109.050 | 109.050 |
| Productos entre precios 100 y 300 | 5.909 | 5.909 |
| Tiempo observado de esa ejecución | 2,2581 s | 1,5700 s |

Son ejecuciones de comprobación, no un nuevo benchmark estadístico ni una comparación equivalente de todas las etapas. Para el primer producto del índice, las cinco distancias KNN coincidieron con fuerza bruta dentro de 1e-7. El original híbrido registró 183 positivos Bloom que el set verificó como falsos y conservó los eventos nuevos.

El monitor procesó 100.000 eventos, con 1.655 compras, cinco ventanas horarias, ocho evaluaciones candidatas CMS y cero evaluaciones candidatas falsas en esa muestra. Reprodujo una alerta para el usuario `554090147`, evento `36883`, ventana `2019-10-01T03:00:00+00:00`, frecuencia estimada y exacta 10. Es evidencia de funcionamiento de la regla de frecuencia en esa muestra, sin acreditar precisión de detección de fraude.

### Casos adicionales que descubren brechas

| Caso ensayado | Resultado observado | Implicación |
|---|---|---|
| Duplicados exactos en las primeras 100K filas originales | `DataFrame.duplicated().sum()` devuelve 17; ambos pipelines reportan 0 duplicados | El ID de fila hace distintas las filas idénticas; hay que definir identidad y política de deduplicación |
| Evento mínimo aceptado por `validate_event`, sin `category_id` | `run_storage_pipeline` falla con `KeyError: 'category_id'` | Validación y almacenamiento no comparten el mismo contrato; también se accede directamente a `category_code` y `brand` |
| Mezcla de `product_id="100"` y `product_id=100` | Streaming falla con `TypeError` al ordenar IDs | Se valida convertibilidad pero no se normaliza; las claves conservan tipos heterogéneos |
| Stream vacío | `ValueError: Se requiere una matriz 2D no vacía` | Falta decidir una salida controlada para vacío o para un lote sin eventos válidos |
| Salida del Heap enviada directamente al monitor | `ValueError: Los eventos deben llegar en orden cronológico` | Debe resolverse la semántica temporal antes de integrar CMS y prioridades |

Los 17 repetidos de contenido requieren una decisión de dominio: dos interacciones con el mismo contenido y timestamp pueden ser acciones reales distintas. No se propone borrarlas ciegamente. La brecha es que hoy el sistema solo reconoce retransmisiones que ya conservan el mismo ID y no documenta suficientemente la política para los registros de origen. También deben revisarse los `assert output == n` de benchmarks si se cambia esa política.

## Reproducibilidad y estado del repositorio

### Diferencia entre carpeta y GitHub main

Los siguientes archivos estaban sin seguimiento al comenzar la revisión y no están en el commit remoto verificado:

```text
src/count_min_sketch.py
src/event_frequency_monitor.py
tests/test_count_min_sketch.py
tests/test_event_frequency_monitor.py
benchmarks/benchmark_count_min_sketch.py
benchmarks/benchmark_frequency_monitor_rees46.py
results/benchmark_count_min_sketch.csv
results/frequency_monitor_alerts.csv
results/frequency_monitor_windows.csv
```

La revisión añade únicamente este informe. Incorporar los archivos a Git deberá hacerse después de revisar su integración y actualizar la documentación; esta auditoría no realizó commits ni push.

### Otros puntos de reproducibilidad

- `requirements.txt` y `requirements-dev.txt` fijan versiones y el entorno instalado supera `pip check`, lo cual es favorable.
- `00_exploracion_rees46.ipynb` importa `pyarrow` y `duckdb` incondicionalmente, pero ninguno aparece en esos archivos de requisitos. El entorno local sí muestra versiones instaladas. Un entorno creado únicamente con lo declarado puede fallar en ese notebook.
- Varios notebooks calculan la raíz mediante `Path.cwd().parent`; funcionan si se lanzan desde `notebooks/`, pero esa condición debe documentarse o hacerse robusta. Desde la raíz pueden buscar los datos en otra carpeta.
- `01_kdtree_knn.ipynb`, celda de índice 10, conserva un `AssertionError` y el código con `atol=1e-8`. Las celdas posteriores explican diferencias de hasta aproximadamente 4,21e-8 y corrigen a 1e-7, pero la aserción inicial sigue ahí. En el entorno guardado, un Run All se detiene antes de alcanzar esa corrección. Hay que consolidar el notebook y reejecutarlo desde cero.
- Los scripts nuevos de CMS y monitor importan `src` sin la preparación de ruta que sí usan otros benchmarks. Conviene documentar y comprobar su ejecución desde la raíz como `python -m benchmarks.benchmark_count_min_sketch` y `python -m benchmarks.benchmark_frequency_monitor_rees46`, o unificar los puntos de entrada. No se ha declarado una instalación limpia satisfactoria.
- El dataset está excluido de Git, lo cual es razonable por tamaño. El README menciona fuente y nombre, pero falta un procedimiento preciso de adquisición, versión/identificador, comprobación de integridad, subconjunto y reglas de preparación.
- No se encontró un workflow de integración continua en los archivos versionados. No es una exigencia explícita de la rúbrica, aunque ayudaría a reproducir las pruebas.

## Entregables y sustentación

| Entregable o condición | Evidencia | Estado |
|---|---|---|
| Repositorio GitHub con código | `main` verificado y código versionado | Presente, con ampliaciones locales pendientes |
| README | Existe y describe limitaciones | Parcial: arquitectura incompleta, familias obligatorias llamadas adicionales y roles pendientes |
| Notebooks | Cinco archivos | Presentes, con una aserción fallida guardada y problemas de instalación/rutas pendientes |
| Diagrama del pipeline | Tabla de etapas en README, sin diagrama encontrado | Falta el diagrama explícito con diez etapas y conexiones reales |
| PDF `Proyecto_Final_[NombreGrupo].pdf`, 8–12 páginas | No encontrado | Falta |
| PDF incluido en GitHub y entregado en campus | No hay PDF en la carpeta ni en el commit | Falta evidencia; la entrega en campus no es verificable desde aquí |
| Presentación de 10–15 diapositivas | No se encontraron PPT/PPTX/PDF de presentación | Falta evidencia local |
| Demo de 3–4 minutos | Ejecuciones parciales de notebooks/scripts | Falta demo integral preparada |
| Exposición de 15 min y preguntas de 10 min | Actividad futura | No evaluable mediante el repositorio |
| Tabla de roles y aportes en README | Texto «Pendiente» | Falta |
| Responsabilidad individual y contribución verificable | Historial con 19 commits visibles y un solo autor | Hay trazabilidad para ese autor; falta declarar integrantes y roles; no acredita por sí solo aportes de otros |

La regla de asignación exige que cada integrante sea responsable principal de al menos dos etapas o de una familia del bloque avanzado. La tabla debe reflejarlo y ser coherente con los aportes. La sustentación incluye preguntas sobre cualquier etapa, no solo la asignada. La rúbrica prevé 0 en sustentación si no se explica lo presentado y 0 en el componente individual por inasistencia injustificada; no se pueden anticipar esos resultados a partir del código.

## Prioridades para cerrar las brechas

### Prioridad 1 Completar el sistema obligatorio

1. Elegir y justificar una técnica de conjuntos y una ANN. Definir sus entradas reales desde el flujo actual, métricas y salida utilizada por recomendaciones.
2. Construir el grafo de productos comprados en una misma orden, con pesos y política temporal/identidad documentados. Resolver la ausencia de `order_id` mediante datos adicionales, simulación o una aproximación expresamente justificada.
3. Implementar PageRank/PPR y comunidades, con sus comparaciones requeridas.
4. Integrar Bloom y CMS con prioridades, índices y salida observable; resolver eventos fuera de orden. Mantener confirmación exacta en decisiones críticas.
5. Definir un solo punto de entrada que demuestre las diez etapas y registre el efecto de un evento en recomendaciones, alertas, ranking y servicio. Si existen ramas, mostrar qué salida consume cada rama y dónde vuelve a usarse.
6. Implementar el servicio/panel y el autocompletado del escenario B. Debe consultar los resultados del sistema y mostrar métricas, no limitarse a gráficos de benchmarks.

### Prioridad 2 Corregir el contrato de datos y la infraestructura

7. Unificar esquema, tipos, campos opcionales y validación. Definir comportamiento de stream vacío y de entradas inválidas.
8. Fijar una política de identidad/deduplicación y probarla con duplicados técnicos y repeticiones de negocio.
9. Implementar o sustentar con el docente una adaptación del requisito de B+Tree en disco. Con el texto actual, la serialización completa en pickle acredita persistencia de una instantánea, pero no cumple plenamente ese índice de disco.
10. Definir prioridades de negocio y mostrar su efecto en procesamiento/latencia. Los agregados invariantes al orden no sustituyen esa evidencia.

### Prioridad 3 Completar evidencia experimental

11. Preparar una matriz por estructura/familia para 1K, 10K, 100K, 1M y 10M, distinguiendo eventos, productos, vectores, nodos y aristas.
12. Automatizar repeticiones y exportación de datos crudos, promedio, desviación, memoria actual/pico, parámetros y plataforma. Justificar las reducciones de repetición.
13. Incorporar recall@K, error de frecuencia, falsos positivos, modularidad y estabilidad según la familia. Ajustar CMS al umbral e interpretar los resultados negativos del híbrido Bloom.
14. Generar gráficos log-log y discutir complejidades, distribución de datos, empates, tamaño de respuesta y límites.

### Prioridad 4 Preparar la entrega académica

15. Redactar el PDF de 8–12 páginas con todas las secciones y referencias originales/de implementación.
16. Crear el diagrama de las diez etapas, tabla de roles, presentación de 10–15 diapositivas y guion de demo de 3–4 minutos.
17. Corregir notebooks y dependencias, comprobar instalación desde cero y ejecución secuencial; actualizar README y registrar/publicar los archivos que formen parte de la entrega.

## Criterio de cierre

La entrega podrá considerarse completa cuando exista una ejecución reproducible que conecte las diez etapas, incluidas las cinco familias avanzadas; estén presentes las comparaciones y escalas exigidas con límites justificados; y se publiquen informe, diagrama, roles y materiales de presentación. Hoy la evidencia permite defender una base funcional de estructuras clásicas, KNN exacto y avances probabilísticos, pero no el cumplimiento completo del proyecto solicitado.
