"""Memoria de construcción de índices, separada de memoria de consultas."""
import argparse
import json
from pathlib import Path
import pandas as pd
import numpy as np
from threadpoolctl import threadpool_limits
from sklearn.preprocessing import StandardScaler
from sklearn.neighbors import KDTree
from benchmarks.benchmark_rubric import measure
from src.ann_index import IVFFlat
from src.set_similarity import MinHashLSH


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--events", nargs="+",type=int,default=[1000,10000,100000,1000000,10000000])
    args=parser.parse_args(); rows=[]
    with threadpool_limits(1):
        for n in args.events:
            path=Path(f"results/complete_rees46_{n}/catalog.json")
            if not path.exists():continue
            records=json.loads(path.read_text(encoding="utf-8"))
            ids=np.array([p["product_id"] for p in records],dtype=np.int64)
            X=StandardScaler().fit_transform(np.log1p([[p["price"],p["views"],p["carts"],p["purchases"]] for p in records]))
            tokens={p["product_id"]:{"brand:"+p["brand"],"category:"+p["category"],"price_bin:"+str(int(np.log1p(p["price"])*2))} for p in records}
            reps=100 if n<=100000 else 3 if n<=1000000 else 1
            for r in range(reps):
                methods={"lsh":lambda:MinHashLSH(32,8).fit(tokens),
                         "ivf":lambda:IVFFlat().fit(ids,X),"kd_tree":lambda:KDTree(X),
                         "exact_sets":lambda:{pid:set(t) for pid,t in tokens.items()}}
                for method,fn in methods.items():
                    value,stats=measure(fn)
                    rows.append({"input_events":n,"products":len(ids),"method":method,"repetition":r,**stats})
                    del value
            print(f"Construcción N={n:,}: {reps} repeticiones",flush=True)
    output=Path('results/rubric');output.mkdir(parents=True,exist_ok=True)
    frame=pd.DataFrame(rows)
    previous=output/'index_build_raw.csv'
    if previous.exists():
        old=pd.read_csv(previous)
        frame=pd.concat([old[~old.input_events.isin(frame.input_events.unique())],frame],ignore_index=True)
    frame.to_csv(previous,index=False)
    frame.groupby(['input_events','products','method']).agg(repetitions=('time_s','count'),
        mean_time_s=('time_s','mean'),std_time_s=('time_s','std'),
        mean_current_mib=('python_current_mib','mean'),mean_peak_mib=('python_peak_mib','mean'),
        max_rss_peak_mib=('rss_peak_mib','max')).reset_index().to_csv(output/'index_build_summary.csv',index=False)


if __name__=='__main__':main()
