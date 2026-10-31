# Investigación y decisiones de diseño

## Estructuras base de las etapas 0 a 5

Con b eventos en un microlote, p productos, u usuarios, z pares de
interacción y B claves por página, las estructuras elegidas son:

| Etapa | Operaciones y costo | Espacio | Alternativa y justificación |
|---|---|---|---|
| FIFO deque | Enqueue y dequeue O(1) | O(b) | Una lista Python con pop(0) desplaza O(b) referencias |
| Ordenación y búsqueda binaria | Ordenación O(b log b), pertenencia O(log b) | O(b) | Un set deduplica en O(b) esperado, pero se implementa el patrón exigido y se restablece orden temporal |
| Heap | Heapify O(b), extracciones O(b log b) | O(b) | Ordenar toda la entrada impide atender microlotes antes del final y retiene O(N) eventos |
| Hash y LRU | Consultas O(1) esperado; peor caso O(p) | O(p) y O(capacidad) | Lista exige búsqueda O(p); LRU explota localidad y puede tener bajo hit rate |
| Matriz CSR | Construcción desde coordenadas, consultas por filas dispersas | O(u+z) | Matriz densa O(up) aunque la mayoría de posiciones esté vacía |
| B+Tree de disco | O(log_B p) páginas por punto; O(log_B p+r/B) por rango | O(p) en disco y caché acotada | Hash no mantiene orden; scan recorre p productos. Inserciones en listas internas añaden O(B) de CPU por nodo |
| KDTree exacto | Construcción típica O(p log p); consulta favorable O(log p+k), peor O(p) | O(pd) | Fuerza bruta O(pd) por consulta; en dimensión alta disminuye la poda del árbol |

Los costos SQL de ingestión se distinguen de las operaciones hash en RAM:
SQLite mantiene tablas exactas con sus propios índices y costos de I/O.
No se afirma O(1) para insertar una clave en SQLite. El B+Tree de precios
es una implementación independiente, con pruebas de reapertura y splits.
La función de normalización usa precio actual, conteos por tipo, log1p
y StandardScaler. Se elige precio actual para no conservar todos los
precios históricos; el pipeline histórico mantiene una mediana exacta
como comparación, con estado que crece con las observaciones.

## Familia probabilística

### Bloom Filter

Bloom [1] representa pertenencia con m bits y h posiciones por clave.
Al insertar se encienden los bits. Una consulta negativa garantiza
ausencia bajo el mismo hash y sin borrados; todos los bits encendidos
solo indican posible pertenencia. Aproximadamente, f=(1-exp(-h n/m))^h.
Se elige m=ceil(-n ln(f)/(ln 2)^2) y h cercano a (m/n)ln 2.
Actualizar y consultar cuestan O(h), y el arreglo usa O(m) bits.

La implementación usa doble hashing determinista BLAKE2b y bytearray.
La sobrecarga Python y el cómputo criptográfico pueden hacerla más lenta
que un set en RAM. Su utilidad aquí es evitar lecturas exactas de disco
para negativos; un positivo se confirma en la tabla `seen` antes de
descartar un evento. La estructura exacta sigue existiendo y no se debe
atribuir al sistema híbrido el ahorro del Bloom aislado. Si se supera
la capacidad esperada aumenta la FPR; no admite borrado seguro.

La comparación usa Hash Set exacto, tiempo, memoria actual/pico y FPR
en 10.000 consultas de claves disjuntas. El experimento histórico
también demuestra que menos verificaciones no implica menor tiempo.
Como referencia se utiliza el trabajo original y la formulación de
Mining of Massive Datasets [8]; la implementación propia está en
`src/bloom_filter.py`, con pruebas contra pertenencia exacta.

### Count Min Sketch

Cormode y Muthukrishnan [2] mantienen d filas de w contadores. Cada
actualización incrementa una celda por fila; la consulta devuelve el
mínimo. Con incrementos no negativos no subestima, salvo overflow o
inconsistencias de clave. Se parametriza w=ceil(e/epsilon),
d=ceil(ln(1/delta)). Bajo los supuestos de hashing, para una consulta
la sobreestimación se acota por epsilon*N con probabilidad al menos
1-delta. La garantía no es simultánea para todas las consultas sin
ajustar delta. Tiempo O(d), espacio O(wd) contadores uint64.

El pipeline cuenta compras por usuario y hora UTC. Usa epsilon=1e-5,
delta=0,01 y umbral 10. Las ventanas forman parte de la clave y no se
eliminan del sketch, por lo que N es el total de compras de la ejecución.
El diccionario exacto persistente confirma los candidatos y emite una
alerta al llegar al umbral. El reordenamiento por prioridad no modifica
la clave horaria. La regla es una señal de actividad, no un clasificador
validado de fraude. El error crece con N; reducir epsilon cuesta memoria.

Se compara con Counter/diccionario. El benchmark de construcción recibe
actualizaciones ponderadas agregadas por producto: conserva el total de
eventos y explicita las claves distintas. No se presenta ese tiempo como
tiempo por evento del monitor online. Se reportan error medio, máximo
y error normalizado. El monitor integrado conserva conteos exactos en
disco y no tiene el ahorro de un CMS aislado. Referencias de funcionamiento:
[2] y la explicación de los autores en DIMACS [9].

## Familia de similitud de conjuntos

Se elige MinHash con LSH [3,4]. Cada producto tiene tokens de marca,
categoría y un intervalo logarítmico de precio. Esta representación
es intencionadamente distinta del vector de comportamiento. Jaccard
es |A intersección B| / |A unión B|. Tokens faltantes se declaran
unknown; compartirlos puede producir semejanzas artificiales y debe
interpretarse con cautela.

Una firma contiene mínimos de permutaciones/hash universales de los
tokens. La fracción de componentes iguales estima Jaccard bajo el
modelo de permutaciones min-wise. Los hashes afines implementados son
una aproximación reproducible a ese modelo. Con s componentes, firma
O(s|A|), espacio O(ps) más tokens y buckets. La dispersión de la
estimación disminuye al aumentar s, a costa de construcción y memoria.

LSH divide la firma en b bandas de r filas, s=br. Una igualdad de banda
genera candidato. Idealmente P(candidato)=1-(1-J^r)^b. El pipeline usa
s=32, b=8, r=4, semilla 42, y refina candidatos con Jaccard exacto.
No completa automáticamente candidatos ausentes mediante fuerza bruta:
puede devolver menos de K y esa pérdida forma parte del recall.

LSH no garantiza tiempo sublineal en el peor caso. Marcas o categorías
dominantes pueden colocar muchos productos en el mismo bucket y llevar
la consulta a O(p). Los tokens y buckets Python consumen más que las
firmas; se distinguen payload y memoria total instrumentada.

La alternativa es recorrer todos los conjuntos y ordenar por Jaccard.
Se usan tiempo, memoria, recall@5 por IDs y una medida adicional que
acepta empates en el umbral exacto. El desempate estable por product_id
evita resultados arbitrarios de sets. Las referencias conceptuales son
Broder [3], Indyk y Motwani [4] y MMDS [8]. El código propio permite
comparar `query(exact=False)` con `query(exact=True)` en el mismo corpus.

## Familia ANN vectorial

Se elige IVF Flat, que separa entrenamiento de centroides, asignación
de vectores a listas invertidas y exploración de listas cercanas. Las
listas invertidas para descriptores visuales aparecen en Sivic y
Zisserman [10]; Faiss [11] documenta IVF Flat y su compromiso nprobe.
Se usa MiniBatchKMeans de scikit-learn [12] para aprender centroides.

Los vectores son [log precio, log vistas, log carritos, log compras],
normalizados sobre la instantánea con StandardScaler. El índice conserva
todos los vectores float32 y sus IDs. Entrena con hasta 50.000 ejemplos
de una muestra con semilla 42, nlist=32 y nprobe=4. Asigna en bloques de
8.192 para evitar una matriz N por nlist residente. Las consultas examinan
las listas de los centroides más cercanos y calculan distancias exactas
dentro de esos candidatos. La aproximación está en omitir otras listas.

Con c centroides, dimensión d, t iteraciones y muestra s, el entrenamiento
cuesta aproximadamente O(tscd); asignar p vectores cuesta O(pcd).
Una consulta cuesta O(cd+qd+q log q) en esta implementación, donde q
es el total de candidatos de las listas consultadas. Con listas equilibradas
q es cercano a p*nprobe/c, pero el peor caso alcanza p. Espacio O(pd+p+cd).
El código ordena distancias dentro de bloques; estos costos de selección
se explicitan y no se reemplazan por una afirmación universal O(log p).

Más nprobe aumenta recall y tiempo. nprobe=nlist examina todo el corpus
y debe coincidir con fuerza bruta, probado con IDs y distancias. La línea
base usa el mismo float32 para separar aproximación de diferencias de
precisión; KDTree exacto float64 aporta una referencia adicional con
tolerancia numérica. Se informa recall@5 estricto y considerando empates.
La calidad se refiere a recuperación geométrica, no a relevancia comercial.

Se prefirió IVF por su mecanismo interpretable, construcción reproducible
y dependencia ya presente. HNSW sería otra elección válida, con mayor
complejidad de grafo y parámetros de conectividad; no se afirma que IVF
domine HNSW. El índice se reconstruye con las instantáneas y no ofrece
actualización online ilimitada de los centroides.

## Familia de influencia

PageRank [5] modela la distribución estacionaria de una caminata con
teleportación. Para amortiguación alpha=0,85 se itera un vector de
probabilidades sobre transiciones ponderadas, distribuyendo masa de
nodos sin salida y normalizando. Una iteración es O(V+E); con t
iteraciones el tiempo es O(t(V+E)) y el estado auxiliar es O(V+E).
No se presenta como un algoritmo de tiempo constante o de una sola pasada.

El grafo no dirigido expresa co-compra por orden. Una arista pesa el
número de órdenes distintas con ambos productos. Un nodo puede tener
influencia por conectarse a productos importantes, no solo por contar
vecinos. Se compara con grado ponderado, calculable en O(V+E). En
grafos no dirigidos conectados, la caminata sin teleportación está muy
relacionada con grado; los rankings pueden coincidir. No se fuerza una
conclusión de superioridad. En componentes desconectadas, alpha y el
vector de teleportación afectan el reparto de masa.

Se usa `networkx.pagerank` como implementación de referencia y se
documenta alpha, tol=1e-8 y max_iter=500 [13]. Los tiempos y Top-10 se
guardan por alternativa. En recomendaciones se suma PageRank a los
candidatos de similitud y co-compra; así la etapa influye en un resultado
del servicio. Su peso actual es heurístico y requiere validación futura
con objetivos y particiones de entrenamiento/evaluación apropiados.

## Familia de comunidades

Louvain [6] optimiza modularidad de forma heurística. Comienza con una
comunidad por nodo, busca movimientos locales de ganancia positiva y
agrega comunidades en supernodos para repetir el proceso. La modularidad
compara peso dentro de comunidades con el esperado bajo un modelo de
grados. No asegura el óptimo global y puede sufrir límite de resolución.
Tiempo práctico cercano a recorridos repetidos de aristas, dependiente
de niveles y convergencia; no se afirma una cota universal O(E).
El grafo y estructuras auxiliares consumen O(V+E).

La alternativa más simple es propagación de etiquetas asíncrona [7].
Cada nodo adopta una etiqueta dominante entre sus vecinos ponderados,
con orden aleatorio controlado. Es sencilla y de bajo costo por barrido
O(V+E), pero puede converger a particiones diferentes o a una comunidad
dominante. Ambas se ejecutan sobre exactamente el mismo grafo, mismos
pesos y semillas documentadas, mediante NetworkX [14].

Se reporta modularidad, tiempo, número y tamaños de comunidades. La
estabilidad se calcula con Adjusted Rand Index entre todas las parejas
de tres ejecuciones con semillas 42,43,44. ARI es invariante a renombrar
etiquetas; no se compara igualdad de números de comunidad. Estabilidad
alta no prueba verdad semántica y una modularidad mayor no garantiza
mejores recomendaciones. Para grafos sin aristas se devuelven singletons,
modularidad 0 por convención y se explicita el caso degenerado.

## Referencias originales e implementaciones de referencia

1. Bloom, B. H. (1970). Space/time trade-offs in hash coding with allowable errors. CACM 13(7), 422-426. https://doi.org/10.1145/362686.362692
2. Cormode, G. y Muthukrishnan, S. (2005). An improved data stream summary: The count-min sketch and its applications. Journal of Algorithms 55, 58-75. https://doi.org/10.1016/j.jalgor.2003.12.001
3. Broder, A. Z. (1997). On the resemblance and containment of documents. SEQUENCES, 21-29. https://doi.org/10.1109/SEQUEN.1997.666900
4. Indyk, P. y Motwani, R. (1998). Approximate nearest neighbors: Toward removing the curse of dimensionality. STOC, 604-613. https://doi.org/10.1145/276698.276876
5. Brin, S. y Page, L. (1998). The anatomy of a large-scale hypertextual Web search engine. Computer Networks 30, 107-117. https://doi.org/10.1016/S0169-7552(98)00110-X
6. Blondel, V. D. et al. (2008). Fast unfolding of communities in large networks. JSTAT P10008. https://doi.org/10.1088/1742-5468/2008/10/P10008
7. Raghavan, U. N., Albert, R. y Kumara, S. (2007). Near linear time algorithm to detect community structures in large-scale networks. PRE 76, 036106. https://doi.org/10.1103/PhysRevE.76.036106
8. Leskovec, Rajaraman y Ullman. Mining of Massive Datasets, 3.ª ed. Libro de referencia disponible en http://www.mmds.org/
9. Cormode. Count-Min Sketch, descripción por sus autores. https://dimacs.rutgers.edu/~graham/pubs/papers/encalgs-cm.pdf
10. Sivic, J. y Zisserman, A. (2003). Video Google: A text retrieval approach to object matching in videos. https://www.robots.ox.ac.uk/~vgg/publications/2003/Sivic03/sivic03.pdf
11. Faiss. The index factory y parámetros de índices IVF. https://github.com/facebookresearch/faiss/wiki/Faiss-indexes
12. scikit-learn. MiniBatchKMeans. https://scikit-learn.org/stable/modules/generated/sklearn.cluster.MiniBatchKMeans.html
13. NetworkX. PageRank. https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.link_analysis.pagerank_alg.pagerank.html
14. NetworkX. Comunidades. https://networkx.org/documentation/stable/reference/algorithms/community.html

La implementación usa NetworkX para los algoritmos de grafo y scikit-learn
para KDTree, escalado y clustering. Bloom, CMS, MinHash/LSH, IVF, Trie y
B+Tree por páginas tienen implementaciones propias. Esta distinción
evita atribuir al grupo código de las bibliotecas de referencia.
