import fs from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';

const root=process.cwd();
const runtime=process.env.EDA_RUNTIME_ROOT || 'C:/Users/bryan/.cache/codex-runtimes/codex-primary-runtime/dependencies';
process.env.RUNTIME_NODE_MODULES=path.join(runtime,'node/node_modules');
const skill=process.env.EDA_PRESENTATIONS_SKILL || 'C:/Users/bryan/.codex/plugins/cache/openai-primary-runtime/presentations/26.1025.11240/skills/presentations';
const {Presentation,PresentationFile}=await import(pathToFileURL(path.join(runtime,'node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs')).href);
const {finalizePresentation,applyPresentationChartFont}=await import(pathToFileURL(path.join(skill,'container_tools/artifact_tool_utils.mjs')).href);
const build=path.join(root,'build/presentation');await fs.mkdir(build,{recursive:true});await fs.mkdir(path.join(root,'reports'),{recursive:true});
const read=async p=>JSON.parse(await fs.readFile(path.join(root,p),'utf8'));
const sizes=[1000,10000,100000,1000000,10000000];
const data=Object.fromEntries(await Promise.all(sizes.map(async n=>[n,await read(`results/complete_rees46_${n}/pipeline_summary.json`)])));
const meta=Object.fromEntries(await Promise.all(sizes.map(async n=>[n,await read(`results/complete_rees46_${n}/run_metadata.json`)])));
const rows=(await fs.readFile(path.join(root,'results/rubric/rubric_summary_100000.csv'),'utf8')).trim().split(/\r?\n/).map(l=>l.split(','));
const headers=rows.shift();const bench=rows.map(r=>Object.fromEntries(headers.map((h,i)=>[h,r[i]])));
const metric=(family,method)=>bench.find(r=>r.family===family&&r.method===method);
const presentation=Presentation.create({slideSize:{width:1280,height:720}});
presentation.theme.defaultFont='Arial';
const C={ink:'#142b40',teal:'#007e80',blue:'#365d91',muted:'#617487',pale:'#eaf4f3'};
const fmt=n=>new Intl.NumberFormat('es-PE').format(n);
let slideNumber=0;
function text(s,value,x,y,w,h,size=25,bold=false,color=C.ink){
 const t=s.shapes.add({geometry:'textbox',position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0}});
 t.text=value;t.text.style={typeface:'Arial',fontSize:size,bold,color};return t;
}
function slide(title,notes=''){
 const s=presentation.slides.add();s.background.fill='#ffffff';slideNumber++;
 text(s,title,70,48,1135,90,44,true);
 text(s,'EDA UTEC 2026-2',70,668,800,25,16,false,C.muted);
 text(s,String(slideNumber).padStart(2,'0'),1160,668,60,25,16,false,C.muted);
 s.speakerNotes.text=notes;return s;
}
function paragraph(s,label,body,y,w=1100){text(s,label,74,y,w,43,29,true,C.teal);text(s,body,74,y+49,w,92,25);}
function chart(s,categories,values,label,x=660,y=190,w=530,h=350){
 const ch=s.charts.add('bar',{position:{left:x,top:y,width:w,height:h},categories,
   series:[{name:label,values:values.map(v=>Number(Number(v).toFixed(4))),fill:C.teal}],hasLegend:false,barOptions:{direction:'column',grouping:'clustered'},
   dataLabels:{showValue:true,position:'outEnd',textStyle:{fontSize:17}},
   xAxis:{textStyle:{fontSize:17}},yAxis:{title:label,textStyle:{fontSize:15},majorGridlines:{fill:'#e0e7ed',width:1}},
   chartFill:'#ffffff',plotAreaFill:'#ffffff'});
 applyPresentationChartFont(ch,{fontFamily:'Arial'});return ch;
}
let s=slide('Pipeline de eventos de comercio electrónico','Apertura 45 s. Problema, objetivo e integración. Fuente: rúbrica del curso y resultados propios. Identificación de integrantes pendiente por el grupo.');
text(s,'Diez etapas integradas',74,210,1110,80,55,true,C.teal);
text(s,'Consulta de productos, recomendaciones,\nactividad de alta frecuencia y co-compra',76,325,1080,125,32);
text(s,'REES46 y simulación reproducible\nGrupo de cuatro integrantes · 2026-2',76,520,1080,70,24,false,C.muted);

s=slide('Datos y alcance de la evaluación','Explicar que 10M eventos no equivale a 10M productos. REES46 no trae order_id. La sesión-hora es un proxy identificado. Fuente: results/complete_rees46_10000000/*.json.');
text(s,'10 millones',74,190,1100,100,80,true,C.teal);
text(s,`filas reales procesadas · ${fmt(data[10000000].products)} productos derivados`,76,300,1100,65,30);
paragraph(s,'Eventos y órdenes','View, cart y purchase reales. Co-compra inferida por sesión y hora UTC.\nLa demo sintética usa órdenes explícitas y prioridades controladas.',400);

s=slide('Arquitectura de las diez etapas','Recorrer el DAG de docs/arquitectura.md. El filtrado lógico de etapa 6 protege actualizaciones. CSR, B+Tree, LSH, IVF y grafo tienen consumidores reales en el servicio. No afirmar que una vista crea una arista de compra.');
const labels=['0 FIFO','1 Limpieza','2 Heap','3 Hash y CSR','4 B+Tree disco','5 KDTree','6 Bloom y CMS','7 LSH e IVF','8 Grafo','9 Servicio'];
for(let i=0;i<10;i++){const col=i%5,row=Math.floor(i/5),x=74+col*229,y=200+row*155;
 const box=s.shapes.add({geometry:'rect',position:{left:x,top:y,width:208,height:95},fill:C.pale,line:{fill:'#92c5c4',width:1}});
 text(s,labels[i],x+12,y+28,186,47,24,true);
}
text(s,'El servicio combina similitud, popularidad, co-compra e influencia.\nLos contadores y trazas permiten observar la participación de cada etapa.',76,548,1100,80,26);

s=slide('Prioridades y estado exacto','Integrantes 1 y 2: 90 s. Complejidades en docs/investigacion.md. Prioridad por microlote, no global sobre un stream infinito. SQLite no tiene costo hash O(1).');
paragraph(s,'Ingreso y limpieza','FIFO por microlote. Normalización, ordenación y búsqueda binaria.\nDigest de contenido y verificación exacta para retransmisiones.',170);
paragraph(s,'Urgencia y almacenamiento','Heap estable para alertas, compras y navegación.\nSQLite conserva historial exacto e interacciones sin retener eventos completos.',350);
text(s,'CSR para popularidad · LRU para consulta · B+Tree por páginas de 4096 bytes',76,565,1110,60,25,true,C.teal);

s=slide('Bloom y Count-Min Sketch','Fuentes originales: Bloom 1970 doi:10.1145/362686.362692; Cormode y Muthukrishnan 2005 doi:10.1016/j.jalgor.2003.12.001. Confirmar positivos en seen y frecuencias exactas. La cota epsilon*N corresponde al total de compras del sketch.');
paragraph(s,'Pertenencia aproximada','Bloom descarta ausencias y exige verificar positivos.\nEl estado exacto se conserva en disco; el ahorro no equivale al filtro aislado.',170);
paragraph(s,'Frecuencia por usuario y hora','CMS puede sobreestimar. Umbral 10, epsilon 1e-5 y delta 0,01.\nLa alerta solo se emite cuando el conteo exacto alcanza el umbral.',350);
text(s,`${fmt(data[10000000].alerts_count)} alertas confirmadas en la ejecución real de 10M`,76,560,1100,65,31,true,C.teal);

s=slide('Conjuntos con MinHash y LSH','Broder 1997 doi:10.1109/SEQUEN.1997.666900; Indyk y Motwani 1998 doi:10.1145/276698.276876. Tokens marca/categoría/precio. Jaccard exacto refina candidatos. Buckets dominantes pueden degradar a recorrido lineal.');
paragraph(s,'Representación','Marca, categoría e intervalo de precio forman un conjunto por producto.\nJaccard mide atributos compartidos; no es distancia vectorial.',170);
paragraph(s,'Candidatos y calidad','32 componentes, ocho bandas, cuatro filas.\nLSH genera candidatos y Jaccard exacto los ordena.',350);
text(s,`Recall@5 en 100K: ${(Number(metric('set_similarity','lsh').recall_at_k)*100).toFixed(1)}% en la muestra de 20 consultas`,76,560,1100,65,30,true,C.teal);

s=slide('Vecinos aproximados con IVF Flat','Referencia conceptual: Sivic y Zisserman 2003 https://www.robots.ox.ac.uk/~vgg/publications/2003/Sivic03/sivic03.pdf; implementación de centroides scikit-learn MiniBatchKMeans. Fuente del gráfico: results/rubric/rubric_summary_100000.csv, lote de 20 consultas.');
text(s,'32 centroides\n4 listas exploradas\n4 características',76,190,520,190,35,true,C.teal);
text(s,'Más nprobe aumenta trabajo y recall.\nExplorar todas las listas es exacto.\nKDTree permanece como referencia.',76,420,520,145,25);
chart(s,['IVF','Fuerza bruta'],[Number(metric('ann','ivf').mean_time_s)*1000,Number(metric('ann','vector_brute').mean_time_s)*1000],'ms / 20 consultas');

s=slide('Influencia en el grafo de co-compra','Brin y Page 1998 doi:10.1016/S0169-7552(98)00110-X. NetworkX PageRank alpha .85, tol 1e-8, max_iter 500. Comparación grado ponderado. No afirmar superioridad si ambos rankings coinciden.');
paragraph(s,'Nodos y aristas','Productos comprados. Cada orden aporta peso a sus pares de productos.\nREES46 usa órdenes inferidas; la simulación las especifica.',170);
paragraph(s,'PageRank frente a grado','La caminata con teleportación pondera relaciones e influencia.\nAmbos rankings se miden sobre el mismo grafo.',350);
text(s,`${fmt(data[10000000].graph.nodes)} nodos y ${fmt(data[10000000].graph.edges)} aristas en 10M`,76,560,1100,60,31,true,C.teal);

s=slide('Comunidades y estabilidad','Blondel et al. 2008 doi:10.1088/1742-5468/2008/10/P10008; Raghavan et al. 2007 doi:10.1103/PhysRevE.76.036106. Tabla/gráfico derivados de results/complete_rees46_1000000/pipeline_summary.json. ARI entre semillas 42,43,44.');
text(s,'Louvain optimiza modularidad.\nPropagación de etiquetas aporta\nuna alternativa más simple.',76,190,540,150,30);
text(s,'Mismo grafo, mismos pesos.\nSe informan cantidad y tamaños\ny estabilidad ARI entre semillas.',76,390,540,145,25);
chart(s,['Louvain','Etiquetas'],data[1000000].graph.comparison.map(r=>r.modularity),'Modularidad');

s=slide('Protocolo experimental','Leer CSV para repeticiones exactas. 100 repeticiones hasta 100K. En escalas mayores la desviación de una sola corrida no es estimable. Instrumentación de tracemalloc afecta tiempos. Memoria de construcción separada de consulta. Equipo compartido, sin aislamiento de carga.');
paragraph(s,'Cinco escalas de entrada','1K, 10K, 100K, 1M y 10M. Eventos, productos y nodos se reportan\npor separado. Semilla 42 y un hilo nativo.',170);
paragraph(s,'Medidas y alternativas','Promedio, desviación y memoria actual/pico. Recall@5, error de frecuencia,\nfalsos positivos, modularidad, tamaños y estabilidad.',350);
text(s,'CSV por repetición y figuras derivadas de mediciones, sin valores transcritos',76,560,1110,60,25,true,C.teal);

s=slide('Escalabilidad integral observada','Fuente: results/complete_rees46_*/run_metadata.json. Cada barra corresponde a una ejecución integral con estado en disco; no son 100 repeticiones del pipeline completo. La comparación de las familias tiene su propio protocolo.');
text(s,`${meta[10000000].elapsed_s.toFixed(1)} s`,76,185,530,95,62,true,C.teal);
text(s,'para procesar 10M eventos',76,287,530,50,27);
text(s,`${meta[10000000].rss_peak_mib.toFixed(1)} MiB`,76,390,530,80,48,true,C.blue);
text(s,'pico RSS muestreado\nEstado exacto en disco; índices en RAM.',76,480,530,90,24);
chart(s,['1K','10K','100K','1M','10M'],sizes.map(n=>Number(meta[n].elapsed_s.toFixed(2))),'Tiempo integral (s)');

s=slide('Demo del servicio integrado','Guion completo en docs/demo_y_sustentacion.md. Demo 3-4 minutos. Ejecutar demo.bat o python -m src.cli serve --events 5000 --port 8766. Mostrar fuente sintética, no confundir con datos reales.');
paragraph(s,'Catálogo y recomendaciones','Autocompletar una marca, filtrar precios y seleccionar un producto.\nContrastar IVF, KNN exacto y las razones del Top-K.',170);
paragraph(s,'Traza, comunidades y alertas','Seguir un evento, explicar las aristas y comparar particiones.\nMostrar una frecuencia estimada y su confirmación exacta.',350);
text(s,'http://127.0.0.1:8766',76,555,1100,65,35,true,C.teal);

s=slide('Conclusiones y responsabilidad del grupo','Distribución propuesta, no prueba de contribución pasada. Integrante 1 etapas0,1,6; integrante2 2,3,4; integrante3 5,7; integrante4 8,9. Nombres y aportes históricos por confirmar. Todos deben defender cualquier etapa.');
paragraph(s,'Resultado','Las diez etapas tienen consumidores observables y una ejecución real de 10M.\nLa aproximación se contrasta con métodos exactos y simples.',170);
paragraph(s,'Límites','Órdenes inferidas, score heurístico, prioridades por microlote\ny reconstrucción por instantáneas. Sin verdad de fraude o relevancia comercial.',350);
text(s,'Cuatro responsabilidades equilibradas y preguntas sobre todo el pipeline',76,560,1110,65,25,true,C.teal);

s=slide('Referencias para la sustentación','Referencias completas con URLs y DOI en docs/investigacion.md y en el informe PDF. Código de grafo: NetworkX. KDTree, escalado y centroides: scikit-learn. Implementaciones propias: Bloom, CMS, LSH, IVF, Trie y B+Tree.');
text(s,'Bloom (1970) y Cormode & Muthukrishnan (2005)\nBroder (1997) e Indyk & Motwani (1998)\nBrin & Page (1998)\nBlondel et al. (2008) y Raghavan et al. (2007)\nSivic & Zisserman (2003)\nNetworkX 3.7, scikit-learn 1.9.1 y documentación Faiss',76,180,1120,350,28);
text(s,'Informe, código, protocolos y resultados crudos en el repositorio del proyecto',76,560,1110,65,25,true,C.teal);

for(let i=0;i<presentation.slides.items.length;i++){
 const png=await presentation.export({slide:presentation.slides.items[i],format:'png',scale:1});
 await fs.writeFile(path.join(build,`slide-${String(i+1).padStart(2,'0')}.png`),new Uint8Array(await png.arrayBuffer()));
}
const candidate=path.join(build,'candidate.pptx');await(await PresentationFile.exportPptx(presentation)).save(candidate);
const finalPath=path.join(root,'reports/Presentacion_Final_Grupo_EDA.pptx');
// Finalizer requires a fresh output; retain an earlier revision under build.
try{await fs.access(finalPath);await fs.rename(finalPath,path.join(build,`previous-${Date.now()}.pptx`));}catch(e){if(e.code!=='ENOENT')throw e;}
const result=await finalizePresentation({workspaceDir:root,candidatePath:candidate,finalPath,
 pythonExecutable:path.join(runtime,'python/python.exe'),
 integrityValidatorPath:path.join(skill,'container_tools/inspect_presentation_package_integrity.py'),
 layoutValidatorPath:path.join(skill,'container_tools/inspect_presentation_layout_geometry.py'),
 layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-bullet-geometry','--validate-heading-fit'],
 explicitTotalSlideCount:14,requiredNativeChartOwnerSlides:[7,9,11],
 materializeLiteralChartWorkbooks:true,
 requiredNativeTableOwnerSlides:[],fontPolicy:{basis:'design',families:['Arial']},
 verifyArtifactToolImport:true,receiptPath:path.join(build,`validation-${Date.now()}.json`)});
if(!result.firstPartyImport?.passed || !result.nativeQuantitativeCharts?.report?.passed)
 throw new Error('La presentación no superó las validaciones de importación y gráficos');
await fs.writeFile(path.join(build,'validation-latest.json'),JSON.stringify(result,null,2));
console.log(JSON.stringify({finalPath,slides:14,sha256:result.finalSha256,validated:true}));
process.exitCode=0;
