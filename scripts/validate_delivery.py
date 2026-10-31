"""Valida coherencia de los artefactos guardados sin repetir benchmarks."""
import csv
import hashlib
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]


def main():
    checks=[]
    def check(name,condition):
        checks.append({'check':name,'passed':bool(condition)})
        if not condition:raise AssertionError(name)
    for n,reps in [(1000,100),(10000,100),(100000,100),(1000000,3),(10000000,1)]:
        folder=ROOT/f'results/complete_rees46_{n}'
        summary=json.loads((folder/'pipeline_summary.json').read_text(encoding='utf-8'))
        catalog=json.loads((folder/'catalog.json').read_text(encoding='utf-8'))
        metrics=summary['metrics']
        check(f'{n}: event conservation',metrics['received']==metrics['output']+metrics['duplicates']+metrics['invalid'])
        check(f'{n}: catalog size',len(catalog)==summary['products'])
        check(f'{n}: interactions conserve weights',sum(p['views']+3*p['carts']+5*p['purchases'] for p in catalog)==summary['csr_weight_sum'])
        check(f'{n}: trace includes all stages',all(t['completed_stages']==list(range(10)) for t in summary['trace']))
        check(f'{n}: trace uses disk index',all(t['snapshot']['price_index_contains_product'] for t in summary['trace']))
        graph=summary['graph']
        check(f'{n}: PageRank normalized',not graph['nodes'] or abs(sum(graph['pagerank'].values())-1)<1e-6)
        check(f'{n}: partitions cover graph',all(sum(c['community_sizes'])==graph['nodes'] for c in graph['comparison']))
        with (ROOT/f'results/rubric/rubric_summary_{n}.csv').open(newline='',encoding='utf-8') as f:
            rows=list(csv.DictReader(f))
        check(f'{n}: 15 methods and repetitions',len(rows)==15 and all(int(r['repetitions'])==reps for r in rows))
    for path in (ROOT/'notebooks').glob('*.ipynb'):
        notebook=json.loads(path.read_text(encoding='utf-8'))
        check(f'{path.name}: no saved errors',all(o.get('output_type')!='error' for c in notebook['cells'] for o in c.get('outputs',[])))
        check(f'{path.name}: executed from code',all(c.get('execution_count') is not None for c in notebook['cells'] if c['cell_type']=='code' and ''.join(c.get('source',[])).strip()))
    ppt=ROOT/'reports/Presentacion_Final_Grupo_EDA.pptx'
    with zipfile.ZipFile(ppt) as z:
        slides=[n for n in z.namelist() if n.startswith('ppt/slides/slide') and n.endswith('.xml') and '/_rels/' not in n]
        workbooks=[n for n in z.namelist() if n.startswith('ppt/embeddings/') and n.endswith('.xlsx')]
        check('PPTX has 14 slides',len(slides)==14)
        check('PPTX has 3 editable chart workbooks',len(workbooks)==3)
    artifacts={}
    for name in ['Proyecto_Final_Grupo_EDA.pdf','Presentacion_Final_Grupo_EDA.pptx']:
        path=ROOT/'reports'/name
        artifacts[name]={'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    output=ROOT/'results/delivery_validation.json'
    output.write_text(json.dumps({'checks':checks,'passed':True,'artifacts':artifacts,
          'scope':'Saved artifact consistency, not a replacement for pytest, visual QA or oral defense'},indent=2),encoding='utf-8')
    print(f'{len(checks)} verificaciones de coherencia aprobadas')


if __name__=='__main__':main()
