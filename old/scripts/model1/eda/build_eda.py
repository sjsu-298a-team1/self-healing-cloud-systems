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
import plot_style as style

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'scripts/model1/data'))
from dataset import load_features, load_scaler, load_manifest, load_case_df, apply_scaler


def build(data_dir, output):
    tables = output / 'data/model1/eda'
    docs = output / 'docs/model1/eda'
    figs = docs / 'figures'
    for p in (tables, figs):
        p.mkdir(parents=True, exist_ok=True)
    style.setup()
    def save(fig, name):
        fig.savefig(figs / (name + '.png'), dpi=150, metadata={'Software': '298-38 EDA'})
        plt.close(fig)
    def csv(frame, name, index=False):
        frame.to_csv(tables / (name + '.csv'), index=index, float_format='%.10g')
    inspection = ROOT / 'data/model1/dataset_inspection'
    cases = pd.read_csv(inspection / 'case_summary.csv')
    missing = pd.read_csv(inspection / 'missing_cells_detail.csv')
    coverage = pd.crosstab(cases.service, cases.fault_type).reindex(columns=['cpu','mem','delay','loss'])
    assert coverage.shape == (5,4) and (coverage.values == 5).all()
    csv(coverage, 'coverage', True)
    save(style.coverage_figure(coverage), '01_coverage')
    mf = missing.groupby('column').n_missing.sum().sort_values()
    mc = missing.groupby('case').n_missing.sum().sort_values()
    assert int(mf.sum()) == 2630
    csv(mf.rename('missing_cells').reset_index(),'missing_by_feature')
    csv(mc.rename('missing_cells').reset_index(),'missing_by_case')
    save(style.bars(mf, 'Missing values are concentrated in a few features',
        '2,630 missing cells across the 100 inspected cases',
        'Top four features shown individually; all remaining features are combined. Source: committed inspection outputs.',
        labels=style.feature_label, top=4, remainder=True), '02_missingness')
    save(style.bars(mc, 'Six cases contain the recorded missing values',
        'Raw missing cells by case · all 100 cases inspected',
        'Cases with zero missing cells are omitted. A missing value differs from an absent schema column.',
        labels=style.case_label), '02b_missingness_cases')
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
    save(style.distributions(raw,stats,representative[:3], 'Cart CPU, memory and latency have different distributions'), '03_distributions')
    save(style.distributions(raw,stats,representative[3:], 'Additional distributions show variability and constant behavior'), '03b_distributions_additional')
    corr=pd.DataFrame(z,columns=features).corr()
    csv(corr,'correlations',True)
    pairs=pd.DataFrame([{'feature_a':features[i],'feature_b':features[j],'pearson_r':corr.iloc[i,j]} for i in range(55) for j in range(i+1,55)]).dropna()
    pairs['absolute_r']=pairs.pearson_r.abs(); pairs=pairs.sort_values('absolute_r',ascending=False,kind='stable')
    csv(pairs,'correlation_pairs')
    save(style.correlations(pairs), '04_correlations')
    fig,ax=plt.subplots(figsize=(16,14),layout='constrained')
    im=ax.imshow(corr,vmin=-1,vmax=1,cmap='RdBu_r')
    ax.set(xticks=range(55),yticks=range(55),xticklabels=features,yticklabels=features,title='Appendix: all 55 training known-normal feature correlations')
    ax.tick_params(labelsize=6); plt.setp(ax.get_xticklabels(),rotation=90); fig.colorbar(im,ax=ax,shrink=.65); save(fig,'04b_full_correlation_matrix')
    timelines=[]
    fig,axes=style.timelines_figure()
    for ax,fault in zip(axes.flat,['cpu','mem','delay','loss']):
        cid=next(c for c in train if c.split('/')[0].endswith('_'+fault))
        df,inj=loaded[cid]; scaled,_=apply_scaler(df,features,scaler)
        service=cid.split('_')[0]
        metric=service+({'cpu':'_cpu','mem':'_mem','delay':'_latency-90','loss':'_latency-90'}[fault])
        values=scaled[:,features.index(metric)]
        t=df.time-df.time.iloc[0]
        style.timeline(ax,t,values,fault,cid,metric)
        timelines.append({'case_id':cid,'feature':metric,'selection':'first lexicographic training case per fault type','pre_median_z':float(np.median(values[t<360])),'post_median_z':float(np.median(values[t>=360])),'post_max_abs_z':float(abs(values[t>=360]).max())})
    from matplotlib.patches import Patch
    fig.legend(handles=[Patch(color='#e4f0f4',label='Known-normal region'),Patch(color='#fff0e3',label='Post-injection evaluation region')],
               loc='lower center',bbox_to_anchor=(.5,.065),ncol=2,frameon=False,fontsize=12)
    save(fig,'05_injection_timelines'); csv(pd.DataFrame(timelines),'timeline_summary')
    extreme=(abs(z)>5)
    counts=pd.Series(extreme.sum(axis=0),index=features).sort_values(ascending=False,kind='stable')
    csv(counts.rename('extreme_cells').rename_axis('feature').reset_index(),'extremes_by_feature')
    ec=pd.DataFrame(case_extremes); csv(ec,'extremes_by_case')
    group=ec.groupby('target_service').extreme_cells.sum().sort_values()
    save(style.bars(counts, 'Which features contribute the most extreme values?',
        f'{int(extreme.sum()):,} cells exceed |z| > 5 in training known-normal data',
        f'Top six features shown; remaining features account for {int(counts.iloc[6:].sum()):,} cells. Descriptive cutoff; no records removed.',
        labels=style.feature_label, xlabel='Cells with |z| > 5', top=6, remainder=False), '06_extreme_values')
    save(style.bars(group, 'Extreme values vary across targeted-service case groups',
        f'{100*extreme.any(axis=1).mean():.2f}% of known-normal training rows contain at least one extreme cell',
        'Each group contains 12 training cases. Counts include all 55 features, not only metrics of the targeted service.',
        labels=lambda x: style.SERVICES.get(x,x), xlabel='Cells with |z| > 5'), '06b_extremes_by_service')
    low=corr.abs().where(~np.eye(55,dtype=bool)).mean().sort_values()
    csv(low.rename('mean_absolute_correlation').rename_axis('feature').reset_index(),'low_correlation_signals')
    for relative,digest in hashes.items(): assert hashlib.sha256((data_dir/relative).read_bytes()).hexdigest()==digest
    summary={'issue':'298-38','structural_cases':100,'telemetry_case_ids_read':train,'raw_input_sha256':hashes,'n_known_normal_rows':len(raw),'n_features':55,'missing_cells_all_cases':int(mf.sum()),'representative_features':representative,'extreme_cells':int(extreme.sum()),'extreme_cell_fraction':float(extreme.mean()),'affected_row_fraction':float(extreme.any(axis=1).mean()),'timeline_examples':timelines,'strongest_pairs':pairs.head(5).to_dict('records'),'low_correlation_signals':low.head(5).to_dict(),'raw_files_unchanged':True,'limitations':['No verified fault-end timestamp.','Correlations are pooled associations, not causal evidence.','No feature, scaler, split, model, threshold or evaluation changes.','All-case structural figures reuse committed inspection outputs; raw telemetry reads are training-only.'],'versions':{'numpy':np.__version__,'pandas':pd.__version__,'matplotlib':matplotlib.__version__}}
    (tables/'summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
    lines=['# Online Boutique EDA findings (298-38)','',
    '## Coverage and missingness','',
    '![Coverage](figures/01_coverage.png)','',
    '100 cases cover 5 target services and 4 fault types, with 5 runs per combination. See coverage.csv. These structural counts reuse the committed inspection artifacts.','',
    '![Missingness](figures/02_missingness.png)','', '![Missingness by case](figures/02b_missingness_cases.png)','',
    f'Exactly {int(mf.sum()):,} raw missing cells are concentrated most in {mf.idxmax()} ({int(mf.max()):,} cells). See missing_by_feature.csv and missing_by_case.csv. Missing cells are distinct from columns absent from a case schema; Model 1 keeps its existing 55 common features.','',
    '## Distributions','', '![Distributions](figures/03_distributions.png)','', '![Additional distributions](figures/03b_distributions_additional.png)','',
    'Raw units and axis ranges differ across CPU, memory and latency signals. Log count axes retain rare tails. The final example is selected by the most training cases with constant behavior; the other examples are fixed semantic CPU/memory/latency choices. Constant within a case does not mean constant across the pooled dataset. feature_statistics.csv records quantiles, skew and constant-case counts for every feature. No missing values are filled for these raw histograms.','',
    '## Correlations','', '![Correlations](figures/04_correlations.png)','',
    f"Strongest pair: {pairs.iloc[0].feature_a} / {pairs.iloc[0].feature_b}, r={pairs.iloc[0].pearson_r:.4f}. Lowest mean absolute correlation: {low.index[0]} ({low.iloc[0]:.4f}). The full matrix is in correlations.csv and figures/04b_full_correlation_matrix.png. Large correlations suggest shared variation, not proven redundancy or causality. No features are removed. Correlations use the existing imputation/scaling function on training known-normal rows only.",'',
    '## Fault injection examples','', '![Timelines](figures/05_injection_timelines.png)','',
    'Examples are selected before examining behavior: the first lexicographic training case for each fault type. CPU uses targeted-service CPU, memory uses memory, and delay/loss use latency-90 as an observable response, not a direct fault label. timeline_summary.csv quantifies each example; these four cases do not establish general fault-type effects. Shading after 360 s means post-injection evaluation region, not confirmed active fault duration.','',
    '## Extreme standardized values','', '![Extremes](figures/06_extreme_values.png)','', '![Extremes by service group](figures/06b_extremes_by_service.png)','',
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
