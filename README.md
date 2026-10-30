# Proyecto EDA UTEC 2026-2

## Pipeline de procesamiento de eventos de comercio electrónico

Proyecto académico del curso **Estructuras de Datos y Algoritmos**, correspondiente a la Maestría en Ciencia de Datos e Inteligencia Artificial de UTEC.

El proyecto implementa y evalúa un pipeline modular de procesamiento de eventos de comercio electrónico utilizando estructuras de datos clásicas, índices especializados y técnicas de procesamiento incremental.

**Dataset:** REES46 – eCommerce Behavior Data  
**Lenguaje:** Python 3.12  
**Entorno:** Visual Studio Code, Jupyter Notebook y Git  
**Estado:** Implementación funcional y experimentación de escalabilidad; revisión académica final pendiente.

---

## 1. Objetivo

Diseñar, implementar y evaluar un sistema capaz de procesar grandes volúmenes de eventos de comercio electrónico, aplicando estructuras de datos adecuadas a distintas operaciones.

La meta de diseño es alcanzar hasta 10 millones de eventos. Sin embargo, la mayor ejecución validada hasta la fecha corresponde a **2 millones de eventos**.

## 2. Arquitectura implementada

El sistema se organiza en etapas:

| Etapa | Estructura o algoritmo | Función |
|---|---|---|
| 0 | Cola FIFO | Ingesta y almacenamiento temporal |
| 1 | Preprocesamiento | Validación, limpieza y deduplicación |
| 2 | MinHeap estable | Priorización de eventos |
| 3 | Hash Table y matriz CSR | Almacenamiento y agregación de interacciones |
| 4 | B+Tree | Consultas por rangos de precios |
| 5 | KD-Tree y KNN exacto | Búsqueda multidimensional de productos |
| 6 | Bloom Filter | Detección probabilística de identificadores observados |

El desarrollo también incluye una implementación de deduplicación híbrida que combina un filtro probabilístico con una verificación exacta.

Las funcionalidades adicionales contempladas en el planteamiento inicial —como MinHash, LSH, HNSW, grafos de co-compra y un servicio de recomendaciones— deberán documentarse por separado conforme se confirme su implementación y alcance.

## 3. Modalidades de procesamiento

### Pipeline original

Integra las etapas de ingesta, preprocesamiento, priorización y construcción de estructuras.

El MinHeap utiliza las siguientes prioridades:

- Alerta crítica sintética: 0.
- Compra (`purchase`): 1.
- Carrito (`cart`): 2.
- Vista (`view`): 3.

Entre eventos de igual prioridad se mantiene el orden FIFO mediante un contador secuencial.

Las alertas críticas son una característica sintética del sistema; no deben interpretarse como etiquetas reales de fraude del dataset REES46.

### Pipeline streaming

La modalidad incremental evita mantener una lista completa de eventos antes de actualizar los acumuladores.

Construye progresivamente información para el catálogo de productos, los contadores de interacciones, la matriz CSR y las características destinadas al KD-Tree.

Esta modalidad no aplica una ordenación global mediante MinHeap. Procesa los eventos aceptados en orden de llegada, lo que permite reducir el almacenamiento temporal de eventos completos.

Se realizaron pruebas para comprobar que determinados resultados agregados permanecen invariantes ante el cambio de orden, incluyendo contadores, matriz CSR, catálogo temporal y medianas de precio.

Esta equivalencia se verificó para los casos ensayados y no implica que ambas modalidades tengan idéntica semántica de ejecución.

## 4. Instalación

### Requisitos previos

- Python 3.12.
- Git.
- Memoria suficiente para el volumen de datos que se desea procesar.

Clonar el repositorio:

```bash
git clone https://github.com/bryanOsmar07/Proyecto_EDA_UTEC.git
cd Proyecto_EDA_UTEC
```

Crear un entorno virtual:

```bash
python -m venv .venv
```

Activar el entorno en CMD de Windows:

```bat
.venv\Scripts\activate
```

Instalar las dependencias principales:

```bash
python -m pip install -r requirements.txt
```

Para ejecutar notebooks y pruebas automatizadas:

```bash
python -m pip install -r requirements-dev.txt
```

## 5. Dataset

Se utiliza REES46, un conjunto de eventos de comportamiento de usuarios en comercio electrónico.

Los eventos contienen información sobre interacciones, usuarios, productos, precios y marcas temporales.

El archivo original utilizado en los experimentos es `2019-Oct.csv`.

Por su tamaño, los datos originales no se incluyen en el repositorio. Deben obtenerse por separado y colocarse en la ubicación esperada por los scripts, dentro de `data/raw/`.

## 6. Ejecución de pruebas

Desde la raíz del proyecto:

```bash
python -m pytest tests/ -q
```

Última ejecución registrada:

**62 pruebas y 5 subtests aprobados.**

Para comprobar específicamente la invariancia de los agregados ante el orden FIFO y MinHeap:

```bash
python -m pytest tests/test_streaming_order_invariance.py -v
```

## 7. Benchmarks

El proyecto incluye mediciones de rendimiento para las estructuras e implementaciones principales.

Para ejecutar el benchmark del pipeline streaming con 100,000 eventos:

```bash
python benchmarks/benchmark_full_pipeline_comparison.py streaming 100000
```

Para ejecutar la variante original:

```bash
python benchmarks/benchmark_full_pipeline_comparison.py original 100000
```

El número final corresponde al límite de eventos que se procesarán.

### Resultados de escalabilidad del pipeline streaming

| Eventos | Tiempo (s) | Throughput (eventos/s) | Incremento pico RSS (MiB) |
|---:|---:|---:|---:|
| 100,000 | 1.6475 | 60,699 | 77.87 |
| 250,000 | 4.1044 | 60,911 | 147.22 |
| 500,000 | 8.6066 | 58,095 | 253.68 |
| 1,000,000 | 17.9340 | 55,760 | 445.78 |
| 2,000,000 | 39.7120 | 50,363 | 826.26 |

**Nota metodológica:** los resultados de 100,000 eventos representan medianas de cinco ejecuciones; los restantes corresponden a una ejecución por volumen. El incremento pico RSS es la diferencia entre el máximo RSS observado y la medición inicial del proceso.

El benchmark de 2 millones registró 81,476 productos en el catálogo y 1,241,370 posiciones no nulas en la matriz CSR.

Los CSV de los experimentos se encuentran en `results/`.

## 8. Consideraciones de complejidad y memoria

La selección de estructuras busca mejorar el costo de operaciones específicas, como búsquedas por clave, consultas por rangos y recuperación de vecinos cercanos.

El pipeline incremental reduce la necesidad de conservar eventos completos durante todas las etapas. Sin embargo, **su consumo de memoria no es constante**.

En particular, la deduplicación exacta conserva identificadores ya observados y el cálculo de medianas exactas conserva información histórica de precios.

El consumo de memoria y el rendimiento pueden variar según la distribución del dataset, el sistema operativo, la configuración del equipo y la implementación de las estructuras.

## 9. Limitaciones

- No se ha validado experimentalmente el procesamiento de 10 millones de eventos.
- El pipeline streaming no preserva la prioridad global del MinHeap original.
- Algunas estructuras y agregadores mantienen estados que crecen con los datos.
- Los benchmarks de mayor volumen todavía requieren repeticiones independientes.
- La reproducibilidad en un entorno limpio debe verificarse antes de la entrega final.
- Las funcionalidades previstas fuera de las etapas verificadas requieren revisión de alcance.

## 10. Organización del repositorio

- `src/`: implementaciones del pipeline, estructuras e índices.
- `tests/`: pruebas automatizadas.
- `benchmarks/`: scripts de evaluación de rendimiento.
- `notebooks/`: exploración, experimentos y análisis.
- `results/`: resultados experimentales en CSV.
- `figures/`: recursos gráficos.
- `reports/`: documentación técnica.
- `data/`: ubicación local de datos, con archivos originales excluidos de Git.

## 11. Integrantes y responsabilidades

**Pendiente:** completar los nombres de los integrantes, las etapas asignadas y las contribuciones verificables de cada participante.

## 12. Estado del proyecto

El proyecto dispone de implementaciones funcionales para las etapas principales descritas, pruebas automatizadas y benchmarks hasta 2 millones de eventos.

Quedan pendientes la verificación de los requisitos completos de la entrega, las pruebas de instalación en un entorno limpio y el cierre de la documentación académica.