# Proyecto EDA UTEC 2026-2

Pipeline de diez etapas para eventos de comercio electrónico. Integra estructuras clásicas, filtrado probabilístico, similitud aproximada, análisis de grafos y un panel local. El punto de entrada final es **`python -m src.cli`**.

Se comprobó una ejecución de **10.000.000 eventos reales REES46**, con **9.993.787 aceptados**, **121.903 productos**, **1.070.614 usuarios** y **5.809.222 posiciones no nulas** en la matriz de interacciones. El tiempo integral fue **1.133,13 s**, con pico RSS muestreado de **1.064,26 MiB** en el equipo descrito en los resultados. Son mediciones de esta ejecución, no garantías generales de rendimiento.

## Inicio rápido

Python 3.12. Desde la raíz del repositorio:

```bash
python -m venv .venv
```

Activar en PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

O en CMD:

```bat
.venv\Scripts\activate
```

Instalar y ejecutar:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest tests/ -q
python -m src.cli serve --events 5000 --port 8766
```

Abrir **http://127.0.0.1:8766**. En Windows también se puede usar `demo.bat`.
La demo no necesita el CSV: usa simulación reproducible, órdenes explícitas,
prioridades de envío, retransmisiones, inventario simulado identificado y
una cuenta con alta frecuencia. El servicio solo escucha en localhost.

**Validación:** 84 pruebas y 5 subtests aprobados, tanto en el entorno del
proyecto como en una instalación nueva creada únicamente desde
`requirements-dev.txt`. `pip check` sin incompatibilidades. El workflow de
GitHub Actions ejecuta la suite sin el dataset.

## Las diez etapas

| Etapa | Implementación | Salida utilizada |
|---|---|---|
| 0 | FIFO con deque | Microlotes que pasan a normalización |
| 1 | Validación, normalización, ordenación y búsqueda binaria | Eventos limpios con identidad explícita |
| 2 | Heap estable por urgencia | Orden de procesamiento dentro del microlote |
| 3 | Hash de catálogo, estado SQLite, matriz CSR y LRU | Características, popularidad, consultas y compras |
| 4 | B+Tree propio en páginas de 4096 bytes y caché LRU acotada | Consultas puntuales y por rango desde el servicio |
| 5 | StandardScaler, KDTree y fuerza bruta exacta | Referencia exacta y vectores para IVF |
| 6 fija | Bloom + confirmación exacta y Count-Min Sketch | Deduplicación global y alertas de frecuencia verificadas |
| 7 fija | MinHash + LSH y IVF Flat | Candidatos de atributos y vecinos vectoriales aproximados |
| 8 fija | Grafo ponderado, PageRank, Louvain y comparación LPA | Co-compra, influencia y comunidades |
| 9 | HTTP local, dashboard, Top-K por Heap, Trie y LRU | Recomendaciones, búsqueda, autocompletado, actividad y alertas |

[Diagrama y contrato del flujo](docs/arquitectura.md) ·
[Investigación y referencias](docs/investigacion.md) ·
[Guion de demo y preguntas](docs/demo_y_sustentacion.md)

La numeración es académica. El filtrado protege las actualizaciones y el
flujo contiene ramas que confluyen en el servicio. No se fuerza a una vista
a crear una arista de compra. Las trazas indican el efecto real de cada evento.

## Dataset y semántica

Fuente: [eCommerce behavior data from multi category store, REES46](https://www.kaggle.com/datasets/mkechinov/ecommerce-behavior-data-from-multi-category-store).
Descargar y descomprimir el archivo de octubre de 2019 en
`data/raw/2019-Oct.csv`. El archivo usado pesa **5.668.612.855 bytes**.
El dataset y los estados de ejecución están excluidos de Git por tamaño.
La huella SHA-256 y el procedimiento de selección están en `results/dataset_manifest.json`.
No se requieren credenciales para ejecutar la demo sintética.

```bash
python -m src.cli run --events 100000 --output results/mi_ejecucion
python -m src.cli run --events 10000000 --batch-size 10000 --output results/mi_ejecucion_10m
python -m src.cli serve --source rees46 --events 100000 --port 8766
```

La identidad técnica de REES46 usa un digest de contenido normalizado.
Filas idénticas se consideran retransmisiones; `source_event_id`, si existe,
permite una identidad externa. Sin ese ID no se distinguen perfectamente
acciones legítimas idénticas y duplicados técnicos. En 100K se eliminan 17
filas repetidas; en 10M se eliminan 6.213 bajo esta política.

REES46 no contiene `order_id`, stock, prioridad de envío ni medios de pago.
El grafo real usa **órdenes inferidas por sesión y hora UTC**, identificadas
como aproximación. La disponibilidad real queda desconocida. La simulación
sí especifica órdenes, urgencia e inventario de demostración.
Los precios conservan la unidad del dataset, sin conversión monetaria.

Las prioridades operan dentro de cada lote: alerta crítica, compra express,
compra estándar/sin urgencia conocida, compra programada, carrito y vista.
El monitor usa la clave usuario-hora UTC y confirma exactamente el umbral
10; una alerta de frecuencia no demuestra fraude real.

## Servicio y consultas

El panel incluye catálogo con rango de precios y autocompletado, comparación
IVF frente a KNN exacto, recomendaciones con razones, trazas, grafo de
co-compra, comunidades y alertas. Sus endpoints de lectura son:

- `/api/summary`: métricas, etapas, alertas y comparación de comunidades.
- `/api/products?q=apple&min=100&max=1000`: B+Tree y catálogo.
- `/api/autocomplete?q=app`: Trie de marcas, categorías e IDs.
- `/api/recommend?product_id=1&k=5`: Top-K con similitud, co-compra e influencia.
- `/api/graph`: vista identificada de hasta 100 nodos, con pesos y comunidades.

Para instantáneas intermedias, añadir `--snapshot-every 100000`. Por defecto
los índices se construyen al final. La reconstrucción se incluye en el tiempo
integral. El servicio entrega consultas sobre la última instantánea construida.

## Experimentos reproducibles

```bash
python -m benchmarks.benchmark_rubric --events 1000 10000 100000 1000000 10000000
python -m benchmarks.benchmark_index_builds
python -m benchmarks.plot_rubric
```

`benchmark_rubric` compara Bloom con set, CMS con Counter, MinHash/LSH con
Jaccard exhaustivo, IVF con fuerza bruta y KDTree, PageRank con grado y
Louvain con propagación de etiquetas en el mismo grafo. Se registran tiempo,
memoria Python actual/pico, RSS actual/pico, FPR, error de frecuencia,
recall@5, modularidad, cantidades/tamaños y estabilidad ARI. La construcción
de índices se mide aparte de las consultas.

La política es 100 repeticiones hasta 100K, tres en 1M y una en 10M por el
costo local de procesamiento e instrumentación en un equipo de 16 GB
compartido. La desviación de una sola observación queda sin estimar.
Las comunidades incluyen además tres semillas para estabilidad.
El número real de repeticiones está en cada CSV.

**N significa eventos de origen.** Los tamaños de catálogos y grafos se
reportan por separado. La consulta de un catálogo derivado de 10M eventos
no equivale a buscar entre 10M vectores distintos. Las consultas cronometradas
usan hasta 20 IDs fijos. Las frecuencias del benchmark se construyen con
actualizaciones ponderadas por producto; el monitor online usa usuario-hora.
No deben mezclarse ambos protocolos.

Resultados nuevos: `results/rubric/`, `results/complete_rees46_*/` y figuras
`figures/*loglog.png`. Cada ejecución integral exporta resumen, catálogo,
recomendaciones y metadatos. Los CSV antiguos conservan experimentos previos;
los notebooks 00–04 son el desarrollo histórico y **05** usa el sistema final.

## Entregables

- [Informe PDF de diez páginas](reports/Proyecto_Final_Grupo_EDA.pdf).
- [Presentación de 14 diapositivas](reports/Presentacion_Final_Grupo_EDA.pptx), con notas de exposición y gráficos editables.
- [Diagrama del pipeline](docs/arquitectura.md).
- [Fundamentos, complejidades, alternativas y referencias](docs/investigacion.md).
- [Demo de cuatro minutos y preguntas para sustentación](docs/demo_y_sustentacion.md).
- [Notebook del sistema completo](notebooks/05_pipeline_completo.ipynb).

La revisión `reports/revision_rubrica_2026-10-30.md` describe el diagnóstico
**anterior a estas implementaciones** y se conserva como referencia histórica.

## Roles y contribuciones de cuatro integrantes

Distribución **propuesta**, pendiente de nombres y de confirmar los aportes
reales. Esta tabla asigna responsabilidades de exposición y mantenimiento;
no inventa contribuciones históricas ni autores de commits.

| Integrante | Etapas propuestas | Aporte que debe sustentar | Evidencia individual |
|---|---|---|---|
| Integrante 1 | 0, 1 y 6 | Esquema, ingesta, limpieza, Bloom, CMS y verificación exacta | Nombre y commits/aportes por confirmar |
| Integrante 2 | 2, 3 y 4 | Prioridades, catálogo, CSR, caché y B+Tree de disco | Nombre y commits/aportes por confirmar |
| Integrante 3 | 5 y 7 | Características, KNN exacto, MinHash/LSH, IVF y recall | Nombre y commits/aportes por confirmar |
| Integrante 4 | 8 y 9 | Grafo, PageRank, comunidades, servicio y demo | Nombre y commits/aportes por confirmar |

Todos deben poder explicar cualquier etapa. Antes de entregar al campus,
completar identificación del grupo e integrantes, verificar las contribuciones
reales y coordinar la exposición individual con las reglas del docente.

## Límites de interpretación

- Procesamiento por microlotes e instantáneas; no hay garantía de latencia de un servicio distribuido infinito.
- Estado exacto en disco; catálogo, índices y grafo consumen RAM según entidades derivadas.
- El CMS no borra ventanas: la cota epsilon*N depende del total de compras del sketch.
- Órdenes inferidas, señales experimentales sin etiquetas de fraude y ranking heurístico sin evaluación comercial.
- B+Tree académico sin eliminación, concurrencia ni recuperación transaccional ante caídas.
- Las mediciones proceden de una máquina compartida con instrumentación y no prueban superioridad universal.

La entrega al campus y la sustentación oral deben realizarlas los integrantes.
