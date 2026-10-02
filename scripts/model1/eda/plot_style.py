"""Readable figures for the existing 298-38 EDA calculations."""
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

BLUE = '#236d8b'
ORANGE = '#bc5627'
INK = '#193348'
SERVICES = {'cartservice':'Cart', 'checkoutservice':'Checkout', 'currencyservice':'Currency',
            'paymentservice':'Payment', 'productcatalogservice':'Product catalog',
            'frontend':'Frontend', 'adservice':'Ad', 'emailservice':'Email',
            'recommendationservice':'Recommendation', 'shippingservice':'Shipping',
            'redis':'Redis', 'istio-init':'Istio init'}
FAULTS = {'cpu':'CPU hog', 'mem':'Memory leak', 'delay':'Network delay', 'loss':'Packet loss'}


def feature_label(value):
    service, metric = value.rsplit('_', 1)
    return SERVICES.get(service, service) + ' · ' + {'cpu':'CPU', 'mem':'memory',
        'latency-90':'p90 latency', 'latency-50':'p50 latency', 'error':'errors',
        'workload':'workload'}.get(metric, metric)


def case_label(value):
    combo, run = value.split('/')
    service, fault = combo.rsplit('_', 1)
    return f'{SERVICES.get(service,service)} · {FAULTS[fault]} · run {run}'


def setup():
    plt.rcParams.update({'font.family':'DejaVu Sans', 'font.size':14, 'axes.titlesize':17,
        'axes.labelsize':13, 'text.color':INK, 'axes.labelcolor':INK,
        'axes.spines.top':False, 'axes.spines.right':False, 'figure.facecolor':'white',
        'savefig.facecolor':'white', 'axes.titleweight':'bold'})


def page(title, subtitle, footnote, size=(12.8,7.2)):
    fig = plt.figure(figsize=size)
    fig.text(.055,.94,title,fontsize=23,weight='bold')
    fig.text(.055,.885,subtitle,fontsize=13,color='#526574')
    fig.text(.055,.035,footnote,fontsize=10,color='#526574')
    return fig


def bars(series, title, subtitle, footnote, labels=None, xlabel='Missing cells', top=None, remainder=False):
    values = series.sort_values(ascending=False, kind='stable')
    if top and len(values)>top:
        rest=values.iloc[top:].sum()
        values=values.iloc[:top].copy()
        if remainder: values.loc['Other features']=rest
    labels = [labels(v) if labels and v!='Other features' else v for v in values.index]
    fig=page(title,subtitle,footnote)
    ax=fig.add_axes([.32,.19,.60,.60])
    ax.barh(range(len(values)),values,color=[BLUE]+['#70a6bb']*(len(values)-1),height=.58)
    ax.set_yticks(range(len(values)),labels=labels)
    ax.invert_yaxis(); ax.set_xlabel(xlabel); ax.set_xlim(0,max(values)*1.20)
    ax.spines[['left','bottom']].set_visible(False)
    ax.tick_params(axis='y',length=0,pad=10); ax.xaxis.set_major_locator(MaxNLocator(5,integer=True))
    ax.grid(axis='x',alpha=.12); ax.set_axisbelow(True)
    for i,value in enumerate(values): ax.text(value+max(values)*.02,i,f'{int(value):,}',va='center',fontsize=15,weight='bold')
    return fig


def coverage_figure(coverage):
    fig=page('100 cases cover every service–fault combination',
        '5 target services × 4 fault types × 5 runs',
        'Source: committed inspection outputs for all 100 cases. Each cell reports the number of runs.')
    ax=fig.add_axes([.25,.17,.69,.63])
    ax.imshow(coverage,cmap='Blues',vmin=0,vmax=7,aspect='auto')
    ax.set(xticks=range(4),xticklabels=[FAULTS[f] for f in coverage.columns],
           yticks=range(5),yticklabels=[SERVICES[s] for s in coverage.index])
    ax.tick_params(length=0,pad=14)
    ax.set_xticks(np.arange(-.5,4,1),minor=True); ax.set_yticks(np.arange(-.5,5,1),minor=True)
    ax.grid(which='minor',color='white',linewidth=4); ax.tick_params(which='minor',length=0)
    for i in range(5):
        for j in range(4): ax.text(j,i,'5 runs',ha='center',va='center',fontsize=20,color='white',weight='bold')
    for spine in ax.spines.values(): spine.set_visible(False)
    return fig


def distributions(raw, stats, selected, title):
    fig=page(title,'Training known-normal data only · raw values, with no imputation',
        'Logarithmic row counts retain rare tails. Raw units and horizontal scales differ between metrics. Missing values excluded.')
    axes=fig.subplots(1,3)
    fig.subplots_adjust(left=.075,right=.97,bottom=.25,top=.72,wspace=.32)
    for ax,f in zip(axes,selected):
        ax.hist(raw[f].dropna(),bins=45,color=BLUE,alpha=.92)
        ax.set_title(feature_label(f),fontsize=16,pad=14)
        ax.set_yscale('log'); ax.set_xlabel('Raw artifact units'); ax.xaxis.set_major_locator(MaxNLocator(4))
        ax.tick_params(labelsize=11); ax.grid(axis='y',alpha=.12)
        ax.text(.0,-.33,f"Skew: {stats.loc[f,'skew']:.2f}\nConstant within {int(stats.loc[f,'train_cases_constant'])} of 60 cases",
                transform=ax.transAxes,fontsize=12,linespacing=1.5)
    axes[0].set_ylabel('Rows (log scale)')
    return fig


def correlations(pairs):
    top=pairs.head(6)
    fig=page('Six strongest feature correlations',
        'Pearson correlation across 21,600 training known-normal rows',
        'Ranked by absolute correlation across all 55 features. Shared variation does not establish causality or justify removal.')
    ax=fig.add_axes([.45,.18,.47,.63])
    labels=[feature_label(r.feature_a)+'\n'+feature_label(r.feature_b) for r in top.itertuples()]
    for i,r in enumerate(top.pearson_r):
        ax.plot([0,r],[i,i],color='#bdd5df',lw=5)
        ax.scatter([r],[i],s=90,color=BLUE,zorder=3)
        ax.text(r+.03,i,f'{r:.4f}',va='center',fontsize=13,weight='bold')
    ax.set(yticks=range(6),yticklabels=labels,xlim=(-1,1.3),ylim=(5.6,-.6),xlabel='Pearson r')
    ax.set_xticks([-1,-.5,0,.5,1]); ax.tick_params(axis='y',length=0,pad=15,labelsize=12)
    ax.spines['left'].set_visible(False); ax.grid(axis='x',alpha=.12)
    return fig


def timelines_figure():
    fig=page('Four training cases around fault injection',
        'Injection starts at 6 minutes · the fault-end time is unknown',
        'First lexicographic training case per fault type. Standardized values use the frozen scaler; these are not model scores.')
    axes=fig.subplots(2,2)
    fig.subplots_adjust(left=.10,right=.97,bottom=.18,top=.76,hspace=.73,wspace=.25)
    return fig,axes


def timeline(ax,t,values,fault,cid,metric):
    ax.axvspan(0,6,color='#e4f0f4'); ax.axvspan(6,12,color='#fff0e3')
    ax.plot(t/60,values,color=BLUE,lw=1.6)
    ax.axvline(6,color=ORANGE,ls='--',lw=1.4)
    ax.set(title=FAULTS[fault]+' · '+feature_label(metric),xlabel='Minutes from case start',
           ylabel='Training z-score',xlim=(0,12))
    ax.set_xticks([0,3,6,9,12]); ax.tick_params(labelsize=11)
    ax.text(.015,.92,'Run '+cid.split('/')[1],transform=ax.transAxes,fontsize=10,va='top')
    ax.grid(axis='y',alpha=.12)
