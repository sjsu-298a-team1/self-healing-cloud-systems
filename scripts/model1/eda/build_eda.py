"""298-38: deterministic descriptive EDA; raw telemetry reads are train-only."""
import argparse
import hashlib
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'scripts/model1/data'))
from dataset import load_features, load_scaler, load_manifest, load_case_df, apply_scaler


def build(data_dir, output):
    tables = output / 'data/model1/eda'
    docs = output / 'docs/model1/eda'
    figs = docs / 'figures'
    for p in (tables, figs):
        p.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({'font.size': 12, 'axes.titlesize': 16, 'figure.dpi': 120})
    def save(fig, name):
        fig.savefig(figs / (name + '.png'), dpi=150, bbox_inches='tight', metadata={'Software': '298-38 EDA'})
        plt.close(fig)
    def csv(frame, name, index=False):
        frame.to_csv(tables / (name + '.csv'), index=index, float_format='%.10g')
    inspection = ROOT / 'data/model1/dataset_inspection'
    cases = pd.read_csv(inspection / 'case_summary.csv')
    missing = pd.read_csv(inspection / 'missing_cells_detail.csv')
    coverage = pd.crosstab(cases.service, cases.fault_type).reindex(columns=['cpu','mem','delay','loss'])
    assert coverage.shape == (5,4) and (coverage.values == 5).all()
    csv(coverage, 'coverage', True)
    fig, ax = plt.subplots(figsize=(12,6))
    ax.imshow(coverage, cmap='Blues', vmin=0, vmax=6, aspect='auto')
    ax.set(xticks=range(4), xticklabels=['CPU hog','Memory leak','Network delay','Packet loss'], yticks=range(5), yticklabels=coverage.index, title='Dataset coverage: 20 combinations, 5 runs each')
    for i in range(5):
        for j in range(4): ax.text(j,i,'5 runs',ha='center',va='center',color='white',fontsize=16)
    fig.tight_layout(); save(fig,'01_coverage')
    mf = missing.groupby('column').n_missing.sum().sort_values()
    mc = missing.groupby('case').n_missing.sum().sort_values()
    assert int(mf.sum()) == 2630
    csv(mf.rename('missing_cells').reset_index(),'missing_by_feature')
    csv(mc.rename('missing_cells').reset_index(),'missing_by_case')
    fig, axes = plt.subplots(1,2,figsize=(16,7), layout='constrained')
    for ax, series, title in zip(axes,[mf,mc],['Missing cells by feature','Missing cells by case']):
        ax.barh(series.index,series.values,color='#24678d'); ax.set_title(title); ax.set_xlabel('Raw missing cells (all 100 cases)'); ax.tick_params(axis='y',labelsize=10)
    save(fig,'02_missingness')
    features, scaler = load_features(), load_scaler()
    train = sorted(load_manifest('train'))
    forbidden = set(load_manifest('val') + load_manifest('test'))
    assert len(train)==60 and not set(train)&forbidden
    raw_parts, z_parts, case_extremes, hashes, loaded = [], [], [], {}, {}
    for cid in train:
        df, injection = load_case_df(str(data_dir),cid)
        assert len(df)==721 and injection-df.time.iloc[0]==360
        normal = df[df.time < injection]
        assert len(normal)==360
        z, _ = apply_scaler(normal,features,scaler)
        raw_parts.append(normal[features]); z_parts.append(z)
        case_extremes.append({'case_id':cid,'target_service':cid.split('_')[0], 'extreme_cells':int((abs(z)>5).sum()),'affected_rows':int((abs(z)>5).any(axis=1).sum())})
        loaded[cid]=(df,injection)
        for name in ['simple_data.csv','inject_time.txt']:
            p=data_dir/cid/name; hashes[cid+'/'+name]=hashlib.sha256(p.read_bytes()).hexdigest()
    raw=pd.concat(raw_parts,ignore_index=True)
    z=np.concatenate(z_parts)
    stats=raw.describe(percentiles=[.01,.5,.95,.99]).T
    stats['skew']=raw.skew(); stats['unique_values']=raw.nunique()
    stats['train_cases_constant']=[sum(x[f].nunique(dropna=True)<=1 for x in raw_parts) for f in features]
    csv(stats,'feature_statistics',True)
    # Fixed semantic CPU/memory/latency examples; one train-only constant-behavior example.
    representative=['cartservice_cpu','cartservice_mem','cartservice_latency-90','frontend_cpu','frontend_mem']
    representative += [next(f for f in stats.sort_values('train_cases_constant',ascending=False,kind='stable').index if f not in representative)]
    fig,axes=plt.subplots(2,3,figsize=(16,9),layout='constrained')
    for ax,f in zip(axes.flat,representative):
        v=raw[f].dropna(); ax.hist(v,bins=45,color='#24678d'); ax.set_title(f,fontsize=13); ax.set_ylabel('Rows (log count)'); ax.set_xlabel('Raw artifact units'); ax.set_yscale('log')
        ax.text(.97,.95,f"skew={stats.loc[f,'skew']:.2f}\nconstant in {int(stats.loc[f,'train_cases_constant'])}/60 cases",transform=ax.transAxes,ha='right',va='top',fontsize=10)
    fig.suptitle('Representative distributions: training known-normal rows only'); save(fig,'03_distributions')
    corr=pd.DataFrame(z,columns=features).corr()
    csv(corr,'correlations',True)
    pairs=pd.DataFrame([{'feature_a':features[i],'feature_b':features[j],'pearson_r':corr.iloc[i,j]} for i in range(55) for j in range(i+1,55)]).dropna()
    pairs['absolute_r']=pairs.pearson_r.abs(); pairs=pairs.sort_values('absolute_r',ascending=False,kind='stable')
    csv(pairs,'correlation_pairs')
    # Slide-readable top correlated pairs, with full 55x55 matrix versioned in CSV.
    fig,ax=plt.subplots(figsize=(14,8),layout='constrained')
    top=pairs.head(12).iloc[::-1]
    ax.barh(top.feature_a+' / '+top.feature_b,top.pearson_r,color='#24678d')
    ax.set(xlim=(-1,1),xlabel='Pearson correlation',title='Strongest telemetry pairs: training known-normal data')
    ax.tick_params(axis='y',labelsize=10); save(fig,'04_correlations')
    fig,ax=plt.subplots(figsize=(14,12),layout='constrained')
    im=ax.imshow(corr,vmin=-1,vmax=1,cmap='RdBu_r')
    ax.set(xticks=range(55),yticks=range(55),xticklabels=features,yticklabels=features,title='All 55 Model 1 features: training known-normal correlations')
    ax.tick_params(labelsize=6); plt.setp(ax.get_xticklabels(),rotation=90); fig.colorbar(im,ax=ax,shrink=.65); save(fig,'04b_full_correlation_matrix')
    timelines=[]
    fig,axes=plt.subplots(2,2,figsize=(16,9),layout='constrained')
    for ax,fault in zip(axes.flat,['cpu','mem','delay','loss']):
        cid=next(c for c in train if c.split('/')[0].endswith('_'+fault))
        df,inj=loaded[cid]; scaled,_=apply_scaler(df,features,scaler)
        service=cid.split('_')[0]
        metric=service+({'cpu':'_cpu','mem':'_mem','delay':'_latency-90','loss':'_latency-90'}[fault])
        values=scaled[:,features.index(metric)]
        t=df.time-df.time.iloc[0]
        ax.axvspan(0,360,color='#dcecf5',label='Known-normal region')
        ax.axvspan(360,720,color='#fff0d6',label='Post-injection evaluation region')
        ax.plot(t,values,color='#174f73',lw=1); ax.axvline(360,color='#ad3333',ls='--')
        ax.set(title=cid+'\n'+metric,xlabel='Seconds from case start',ylabel='Frozen training z-score')
        timelines.append({'case_id':cid,'feature':metric,'selection':'first lexicographic training case per fault type','pre_median_z':float(np.median(values[t<360])),'post_median_z':float(np.median(values[t>=360])),'post_max_abs_z':float(abs(values[t>=360]).max())})
    handles,labels=axes[0,0].get_legend_handles_labels(); fig.legend(handles,labels,loc='outside lower center',ncol=2)
    fig.suptitle('Four training examples; injection at 360 s; fault end unknown'); save(fig,'05_injection_timelines'); csv(pd.DataFrame(timelines),'timeline_summary')
    extreme=(abs(z)>5)
    counts=pd.Series(extreme.sum(axis=0),index=features).sort_values(ascending=False,kind='stable')
    csv(counts.rename('extreme_cells').rename_axis('feature').reset_index(),'extremes_by_feature')
    ec=pd.DataFrame(case_extremes); csv(ec,'extremes_by_case')
    group=ec.groupby('target_service').extreme_cells.sum().sort_values()
    fig,axes=plt.subplots(1,2,figsize=(16,7),layout='constrained')
    top=counts.head(12).iloc[::-1]; axes[0].barh(top.index,top,color='#24678d'); axes[0].set_title('Features contributing most extreme cells'); axes[0].tick_params(axis='y',labelsize=10)
    axes[1].barh(group.index,group,color='#24678d'); axes[1].set_title('Concentration by targeted-service case group')
    for ax in axes: ax.set_xlabel('Cells with |z| > 5 (descriptive only)')
    fig.suptitle('Training known-normal variability; no records removed'); save(fig,'06_extreme_values')
    low=corr.abs().where(~np.eye(55,dtype=bool)).mean().sort_values()
    csv(low.rename('mean_absolute_correlation').rename_axis('feature').reset_index(),'low_correlation_signals')
    for relative,digest in hashes.items(): assert hashlib.sha256((data_dir/relative).read_bytes()).hexdigest()==digest
    summary={'issue':'298-38','structural_cases':100,'telemetry_case_ids_read':train,'raw_input_sha256':hashes,'n_known_normal_rows':len(raw),'n_features':55,'missing_cells_all_cases':int(mf.sum()),'representative_features':representative,'extreme_cells':int(extreme.sum()),'extreme_cell_fraction':float(extreme.mean()),'affected_row_fraction':float(extreme.any(axis=1).mean()),'timeline_examples':timelines,'strongest_pairs':pairs.head(5).to_dict('records'),'low_correlation_signals':low.head(5).to_dict(),'raw_files_unchanged':True,'limitations':['No verified fault-end timestamp.','Correlations are pooled associations, not causal evidence.','No feature, scaler, split, model, threshold or evaluation changes.','All-case structural figures reuse committed inspection outputs; raw telemetry reads are training-only.'],'versions':{'numpy':np.__version__,'pandas':pd.__version__,'matplotlib':matplotlib.__version__}}
    (tables/'summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
    lines=['# Online Boutique EDA findings (298-38)','',
    '## Coverage and missingness','',
    '![Coverage](figures/01_coverage.png)','',
    '100 cases cover 5 target services and 4 fault types, with 5 runs per combination. See coverage.csv. These structural counts reuse the committed inspection artifacts.','',
    '![Missingness](figures/02_missingness.png)','',
    f'Exactly {int(mf.sum()):,} raw missing cells are concentrated most in {mf.idxmax()} ({int(mf.max()):,} cells). See missing_by_feature.csv and missing_by_case.csv. Missing cells are distinct from columns absent from a case schema; Model 1 keeps its existing 55 common features.','',
    '## Distributions','', '![Distributions](figures/03_distributions.png)','',
    'Raw units and axis ranges differ across CPU, memory and latency signals. Log count axes retain rare tails. The final example is selected by the most training cases with constant behavior; the other examples are fixed semantic CPU/memory/latency choices. Constant within a case does not mean constant across the pooled dataset. feature_statistics.csv records quantiles, skew and constant-case counts for every feature. No missing values are filled for these raw histograms.','',
    '## Correlations','', '![Correlations](figures/04_correlations.png)','',
    f"Strongest pair: {pairs.iloc[0].feature_a} / {pairs.iloc[0].feature_b}, r={pairs.iloc[0].pearson_r:.4f}. Lowest mean absolute correlation: {low.index[0]} ({low.iloc[0]:.4f}). The full matrix is in correlations.csv and figures/04b_full_correlation_matrix.png. Large correlations suggest shared variation, not proven redundancy or causality. No features are removed. Correlations use the existing imputation/scaling function on training known-normal rows only.",'',
    '## Fault injection examples','', '![Timelines](figures/05_injection_timelines.png)','',
    'Examples are selected before examining behavior: the first lexicographic training case for each fault type. CPU uses targeted-service CPU, memory uses memory, and delay/loss use latency-90 as an observable response, not a direct fault label. timeline_summary.csv quantifies each example; these four cases do not establish general fault-type effects. Shading after 360 s means post-injection evaluation region, not confirmed active fault duration.','',
    '## Extreme standardized values','', '![Extremes](figures/06_extreme_values.png)','',
    f'{int(extreme.sum()):,} of {extreme.size:,} training known-normal cells exceed |z| > 5 ({100*extreme.mean():.3f}%), affecting {100*extreme.any(axis=1).mean():.2f}% of rows. Largest feature contributor: {counts.index[0]} ({int(counts.iloc[0])} cells). Largest targeted-service group: {group.idxmax()} ({int(group.max())} cells). See extremes_by_feature.csv and extremes_by_case.csv. This reuses the demo’s descriptive cutoff, not a model threshold; no records are removed.','',
    '## Boundaries','',
    'All detailed EDA uses only the 60 training cases. Validation/test raw files and model performance are not read. Correlations, distributions and outlier analysis use the 21,600 known-normal training rows; timelines alone show full selected training cases. Raw-file hashes are verified unchanged before/after. There is no verified fault-end timestamp, and results are descriptive rather than evidence of model performance.','']
    report='\n'.join(lines)
    import re
    report=re.sub(r'(?<![/\w])([a-z_]+\.csv)', r'[\1](../../../data/model1/eda/\1)', report)
    report=report.replace('figures/04b_full_correlation_matrix.png.', '[full matrix figure](figures/04b_full_correlation_matrix.png).')
    report += '\nSee [reproduction instructions and artifact index](README.md) and [provenance summary](../../../data/model1/eda/summary.json).\n'
    (docs/'findings.md').write_text(report)
    print(json.dumps({k:summary[k] for k in ['n_known_normal_rows','extreme_cells','affected_row_fraction','raw_files_unchanged']}))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data-dir',required=True,type=Path)
    p.add_argument('--output-root',type=Path,default=ROOT)
    a=p.parse_args(); build(a.data_dir.expanduser().resolve(),a.output_root.expanduser().resolve())
