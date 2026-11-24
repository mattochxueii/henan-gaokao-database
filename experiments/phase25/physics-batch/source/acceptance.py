from pathlib import Path
import json
import sys
from gaokao import ROOT, read_json, digest, require
from analysis_db import fingerprint
from storage import atomic_json
from core.review_board import replay
from core.batch_planner import shingles,check
from core.science_workflow import check_publication
from pypdf import PdfReader
b=ROOT/'experiments/phase25/physics-batch'
archives=[]
for phase in (14,21,22,24):
    for p in (ROOT/'experiments'/f'phase{phase}'/'physics').glob('blind-packet.json'):
        archives.extend((p.relative_to(ROOT).as_posix(),q['order'],q['stem']) for q in read_json(p)['paper']['questions'])
sys.path.insert(0,str(ROOT/'experiments/phase21/source'))
from make_candidate import parse_markdown
for name in ('phase22/source/physics.md','phase24/source/physics-revisions.md'):
    p=ROOT/'experiments'/name
    archives.extend((name,n,stem) for n,_,stem,*_ in parse_markdown(p.read_text(encoding='utf8')))
candidates=[read_json(b/s/'round3/candidate.json') for s in "AB"]
record={'scope':'两个独立宿主出卷样本，三名隔离AI角色。教师0，学生0。','archives_compared':len(archives),
        'frozen':{str(p.relative_to(ROOT)).replace('\\','/'):digest(p) for p in
                  [ROOT/'forecast/frozen/henan-2027-math-v3.json',ROOT/'forecast/preregistered/2027-math-trends.json']},
        'archive_count':len(list((ROOT/'data/papers').glob('*/*.json'))),
        'batch':check(read_json(b/'plan-v2.json'),candidates),'papers':{}}
for s in 'AB':
    dest=b/s/'published'
    doc=check_publication(dest,read_json(dest/'publication.json'))
    rows=[]
    for q in doc['questions']:
        x=shingles(q['stem'])
        nearest=max((len(x&y)/len(x|y),p,i) for p,i,text in archives for y in [shingles(text)])
        rows.append({'number':q['order'],'nearest':nearest[1],'position':nearest[2],'stem_jaccard':round(nearest[0],4)})
    require(max(r['stem_jaccard'] for r in rows)<.58,'旧卷高度相似')
    require(replay(dest/'board')['status']=='eligible','没有达到门槛')
    record['papers'][s]={'archive_comparison':rows,'score_history':[{
        k:r[k] for k in ('round','final_score','fatal_count','status','rewrite','locked')
    } for n in (1,2,3) for r in [read_json(dest/'board'/f'scorecard-round{n}.json')]],
    'choice_figures':[q['order'] for q in doc['questions'] if q['options'] and q['figure']],
    'pages':{g:len(PdfReader(dest/(g+'.pdf')).pages) for g in ('paper','solutions')},
    'sha256':{g:digest(dest/(g+'.pdf')) for g in ('paper','solutions')}}
atomic_json(b/'acceptance.json',record)
print(record['archive_count'],record['frozen'])
for s,r in record['papers'].items():print(s,r['pages'],max(i['stem_jaccard'] for i in r['archive_comparison']),r['score_history'])
