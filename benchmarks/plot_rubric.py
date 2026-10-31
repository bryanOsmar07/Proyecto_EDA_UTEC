"""Figuras derivadas exclusivamente de CSV y JSON medidos."""
import json
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    out=Path('figures');out.mkdir(exist_ok=True)
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    frames=[pd.read_csv(p) for p in sorted(Path('results/rubric').glob('rubric_summary_*.csv'))]
    if frames:
        frame=pd.concat(frames,ignore_index=True)
        frame.to_csv('results/rubric/all_summary.csv',index=False)
        families=['membership','frequency','set_similarity','ann','influence','communities']
        fig,axes=plt.subplots(2,3,figsize=(13,7.5))
        labels={'membership':'Pertenencia','frequency':'Frecuencia ponderada','set_similarity':'Conjuntos / 20 consultas',
                'ann':'Vectores / 20 consultas','influence':'Influencia','communities':'Comunidades'}
        for family,ax in zip(families,axes.flat):
            for method,g in frame[frame.family==family].groupby('method'):
                g=g.sort_values('input_events');ax.loglog(g.input_events,g.mean_time_s,marker='o',label=method)
            ax.set_title(labels[family]);ax.set_xlabel('Eventos de origen N');ax.set_ylabel('Tiempo medio (s)')
            ax.grid(alpha=.2,which='both');ax.legend(fontsize=8)
        fig.suptitle('Escalabilidad sobre corpus derivados de REES46',fontsize=15)
        fig.tight_layout();fig.savefig(out/'rubric_scalability_loglog.png',dpi=180);plt.close(fig)
        quality=frame[(frame.family.isin(['ann','set_similarity'])) & frame.method.isin(['ivf','lsh'])]
        fig,ax=plt.subplots(figsize=(7.5,3.7))
        for method,g in quality.groupby('method'):
            g=g.sort_values('input_events');ax.semilogx(g.input_events,g.recall_at_k,marker='o',label=method+' IDs')
            ax.semilogx(g.input_events,g.tie_aware_recall,marker='x',linestyle='--',label=method+' con empates')
        ax.set_ylim(0,1.05);ax.set_xlabel('Eventos de origen N');ax.set_ylabel('Recall@5 en 20 consultas');ax.legend();ax.grid(alpha=.2)
        fig.tight_layout();fig.savefig(out/'rubric_recall.png',dpi=180);plt.close(fig)
    rows=[]
    for p in Path('results').glob('complete_rees46_*/run_metadata.json'):
        d=json.loads(p.read_text());s=json.loads((p.parent/'pipeline_summary.json').read_text())
        rows.append({**d,'accepted_events':s['metrics']['output'],'duplicates':s['metrics']['duplicates'],'csr_nnz':s['csr_nnz']})
    if rows:
        df=pd.DataFrame(rows).sort_values('requested_events');df.to_csv('results/rubric/end_to_end.csv',index=False)
        fig,axes=plt.subplots(1,2,figsize=(10,3.5));axes[0].loglog(df.requested_events,df.elapsed_s,'o-',color='#007e80');axes[0].set_ylabel('Tiempo integral (s)')
        axes[1].loglog(df.requested_events,df.rss_peak_mib,'o-',color='#385c91');axes[1].set_ylabel('Pico RSS (MiB)')
        for ax in axes:ax.set_xlabel('Eventos recibidos');ax.grid(alpha=.2,which='both')
        fig.tight_layout();fig.savefig(out/'complete_pipeline_loglog.png',dpi=180);plt.close(fig)


if __name__=='__main__':main()
