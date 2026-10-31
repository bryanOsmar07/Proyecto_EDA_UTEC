# Demo y sustentación

## Preparación

Ejecutar `python -m src.cli serve --events 5000 --port 8766` y abrir
http://127.0.0.1:8766. En Windows también se puede ejecutar `demo.bat`.
No se necesita descargar REES46 para esta demo: contiene órdenes
sintéticas explícitas, retransmisiones y una cuenta con alta frecuencia.
Para datos reales usar `--source rees46 --data data/raw/2019-Oct.csv`.

## Guion de cuatro minutos

| Tiempo | Acción | Qué demostrar |
|---|---|---|
| 0:00 a 0:30 | Mostrar métricas y origen | Diferenciar simulación y REES46; recibidos, aceptados, duplicados y compras |
| 0:30 a 1:10 | Abrir las diez etapas y una traza | FIFO, normalización, prioridad por microlote, índices y efectos posteriores de un evento |
| 1:10 a 2:10 | Buscar una marca con autocompletado, restringir precio y seleccionar producto | Trie, B+Tree de disco, LRU y Top-K; comparar vecinos IVF con KNN exacto y explicar Jaccard |
| 2:10 a 3:00 | Abrir grafo y comunidades | Aristas por orden, peso, PageRank, modularidad y estabilidad Louvain frente a LPA |
| 3:00 a 3:40 | Abrir alertas | Usuario por hora UTC, candidato CMS y conteo exacto; no bloquear por un positivo probabilístico |
| 3:40 a 4:00 | Mostrar resultados guardados | Escala 10M, RAM medida y límites de repetición; distinguir productos de eventos |

El pipeline no necesita que todo evento sea una compra. Una vista actualiza
popularidad y características, mientras una compra puede modificar órdenes
y aristas. En la traza se distingue esta semántica del simple paso por una
función. La prioridad es local al microlote, no global sobre un stream infinito.

## Distribución propuesta entre cuatro integrantes

Los identificadores son provisionales. La distribución es un plan equilibrado
de exposición y responsabilidad, solicitado por el grupo; no acredita aportes
históricos. Completar nombres y evidencias reales antes de entregar.

| Integrante | Responsabilidad propuesta | Tiempo de exposición |
|---|---|---:|
| Integrante 1 | Etapas 0, 1 y 6; esquema, deduplicación, Bloom y CMS | 3 min |
| Integrante 2 | Etapas 2, 3 y 4; prioridad, catálogo, CSR, LRU y B+Tree de disco | 3 min |
| Integrante 3 | Etapas 5 y 7; KNN exacto, MinHash/LSH e IVF, evaluación de recall | 3 min |
| Integrante 4 | Etapas 8 y 9; PageRank, comunidades, servicio y conclusiones | 3 min |

Reservar tres minutos adicionales para apertura, transiciones y cierre en
la exposición de 15 minutos. La demo debe coordinarse con esas intervenciones
según el formato que indique el docente. Preparar además diez minutos de
preguntas y practicar todo el flujo, no solo la parte asignada.

## Preguntas para practicar

1. ¿Por qué un positivo Bloom requiere confirmación? ¿Qué estructura conserva exactitud?
2. ¿Qué cambia en la FPR si el filtro recibe más claves que su capacidad esperada?
3. ¿Cuál es la clave del CMS y a qué N se aplica epsilon*N? ¿Por qué no equivale a una ventana deslizante?
4. ¿Por qué se comparan actualizaciones ponderadas por separado del monitor online?
5. ¿Qué garantía ofrece MinHash y qué aproximación añade LSH? ¿Qué ocurre con buckets enormes?
6. ¿Cómo afecta nprobe al recall y cuándo IVF se vuelve exacto?
7. ¿Por qué dos KNN exactos pueden devolver IDs diferentes con las mismas distancias?
8. ¿Qué parte del B+Tree está en disco? ¿Cuánto puede crecer su caché? ¿Por qué pickle no era suficiente?
9. ¿La prioridad de microlote equivale a prioridad global? ¿Qué latencia añade esperar el lote?
10. ¿Por qué sesión no equivale a orden? ¿Qué sesgo introduce la aproximación horaria?
11. ¿Qué añade PageRank frente al grado ponderado en un grafo no dirigido?
12. ¿Qué mide modularidad? ¿Una comunidad estable es necesariamente una comunidad real?
13. ¿Cómo se calcula ARI y por qué no se comparan etiquetas numéricas directamente?
14. ¿Qué estados están en disco y cuáles crecen en RAM? ¿Qué significa pico RSS muestreado?
15. ¿Qué prueba recorrer 10M eventos y qué no prueba sobre un índice con menos productos?
16. ¿Qué parte del ranking es heurística y qué datos se necesitarían para validar utilidad comercial?

Las respuestas deben apoyarse en `docs/investigacion.md`, código, parámetros
y CSV medidos. Evitar memorizar una cifra sin entender su protocolo.
