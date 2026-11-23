"""Normalize saved English exam text by explicitly verified section transitions."""
from pathlib import Path
import argparse
import re

import bootstrap  # noqa: F401
from core.paper_intake import ingest
from gaokao import ROOT, require
from import_public_chinese import ZH_REGIONS

# The coordinates address the saved UTF-8 snapshots, including extracted original page breaks.
# Lists cover A–D, gap matching, cloze, grammar, application and continuation in order.
SPANS = {
 "en20": ([(11,30),(32,49),(51,67),(69,87),(90,101),(105,123),(126,128),(131,139),(141,156)], (158,220)),
 "en21": ([(214,248),(265,303),(335,375),(413,451),(486,516),(555,595),(681,700),(755,768),(793,829)], None),
 "en22": ([(79,112),(114,163),(165,207),(209,260),(264,292),(298,331),(334,355),(358,368),(370,402)], (407,416)),
 "en23": ([(19,49),(51,87),(89,122),(124,159),(162,187),(191,224),(227,242),(245,260),(262,295)], (320,383)),
 "en24": ([(136,158),(160,175),(177,196),(198,216),(219,230),(234,252),(255,258),(261,270),(272,281)], None),
 "en25": ([(11,61),(63,95),(97,131),(133,169),(172,198),(202,234),(237,256),(259,279),(281,305)], (334,398)),
 "en26": ([(75,94),(96,112),(114,133),(135,155),(158,169),(173,191),(194,196),(199,204),(206,215)], (225,237)),
}
URLS = {
 "en20":"https://zy.21cnjy.com/11669066",
 "en21":"https://m.jszs.com/uploads/file/202312/05/1701770312349144.pdf",
 "en22":"https://zy.21cnjy.com/12396223",
 "en23":"https://static-gkcx.gaokao.cn/upload/zhenti/20230611/1686478920_1060.pdf",
 "en24":"https://zy.21cnjy.com/20568421",
 "en25":"https://static-gkcx.gaokao.cn/upload/zhenti/20250611/1749605734_7546.pdf",
 "en26":"https://zy.21cnjy.com/25946873",
}
OPTION = re.compile(r"(?:^|(?<=[\s.?!;。’”]))([A-G])[\.．,]\s*", re.M)
ANSWER_SLOTS = re.compile(r"(?<!\d)([1-6]?\d)[.．]\s*([A-G])(?=[\s\d【]|$)")
WATERMARK = re.compile(r"^\s*(?:第\s*\d+\s*页\s*/\s*共\s*\d+\s*页|学科\s*网.*股份有限\s*公司|学科网（北京）股份有限公司)\s*$")
ENGLISH_WRITINGS = {20:[(203,210),(214,220)],21:[(769,776),(830,846)],
                    22:[(307,315),(318,328)],23:[(355,366),(373,383)],24:[(44,57),None],
                    25:[(370,380),(384,398)],26:[(366,369),(381,386)]}


def clean(lines):
    return "\n".join(line.strip() for line in lines
                     if line.strip() and not line.strip().isdigit() and not WATERMARK.fullmatch(line))


def split_options(text, keys):
    parts=list(OPTION.finditer(text))
    assert ''.join(m[1] for m in parts)==keys, ("选项不完整", keys, text[:65], [m[1] for m in parts])
    return text[:parts[0].start()].strip(), {
        m[1]:re.sub(r"\s+"," ",text[m.end():parts[i+1].start() if i+1<len(parts) else len(text)]).strip()
        for i,m in enumerate(parts)}


def numbered(text, sequence, option_keys="ABCD"):
    hits=list(re.finditer(r"(?m)^\s*(\d{1,2})[.．]\s*",text))
    hits=[m for m in hits if int(m[1]) in sequence]
    assert [int(m[1]) for m in hits]==list(sequence), ("题号不连续",list(sequence),[int(m[1]) for m in hits])
    out=[]
    for i,m in enumerate(hits):
        block=text[m.end():hits[i+1].start() if i+1<len(hits) else len(text)]
        stem,options=split_options(block,option_keys)
        out.append((int(m[1]),stem,options))
    return text[:hits[0].start()].strip(),out


def key_answers(lines, first, last):
    """Extract a key limited to an explicitly identified answer range."""
    line=clean(lines[first-1:last]).replace("【答案】"," ")
    return {int(n): a for n,a in ANSWER_SLOTS.findall(line)}


def answers(lines, name, window):
    yr=int(name[2:])
    if yr==24:
        key="".join(re.sub(r"[^A-G]","",lines[i].split("：")[-1].split(":")[-1]) for i in (1,2,3))
        assert len(key)==35,key
        opts=dict(zip(range(21,56),key))
        grammar={int(n):txt for n,txt in re.findall(r"(?m)^(5[6-9]|6[0-5])\.([A-Za-z][A-Za-z /]+)$",clean(lines[7:34]))}
        for n,value in grammar.items():
            if n not in (56,62,63) and f'{n}.{value}' in lines:
                grammar[n]=value[0].lower()+value[1:]
    elif yr==22:
        opts=key_answers(lines,407,414)
        grammar=extract_grammar(clean(lines[414:416]),56)
    elif yr==21:
        opts={}
        for a,b in [(249,249),(304,304),(376,376),(452,452),(517,517),(596,598)]:
            opts.update(key_answers(lines,a,b))
        grammar=extract_grammar(clean(lines[700:706]).replace("【答案】",""),56)
    else:
        a,b=window
        first=21 if yr in (22,26) else 1
        if yr==20:
            opts={}
            for l in lines[a-1:192]:
                if m := re.match(r"^\s*(\d{1,2})\.\s*([A-G])\s*(?:[【 ]|详解|$)",l):
                    opts[int(m[1])]=m[2]
            grammar=extract_grammar(clean(lines[192:202]),36)
        else:
            opts=key_answers(lines,a,{22:293,23:343,25:354,26:234}[yr])
            grammar=extract_grammar(clean(lines[{22:294,23:345,25:359,26:235}[yr]:{22:304,23:351,25:366,26:237}[yr]]),first+35)
    if yr == 22:
        grammar[60] = "is designed"
    if yr == 24:
        for n in (56,62):
            grammar[n] = grammar[n].lower()
    expected=range(21,56) if yr in (21,22,24,26) else range(1,36)
    assert all(n in opts for n in expected),("客观题答案缺失",name,sorted(set(expected)-opts.keys()))
    assert len(grammar)==10,("语法答案缺失",name,grammar)
    return opts,grammar


def extract_grammar(text, start):
    marks=list(re.finditer(r"(?<!\d)(\d{2})[．.]\s*",text))
    values={}
    for i,m in enumerate(marks):
        number=int(m[1])
        if not start<=number<start+10:
            continue
        raw=text[m.end():marks[i+1].start() if i+1<len(marks) else len(text)]
        key=re.match(r"\s*([a-zA-Z][a-zA-Z' /-]*)",raw)
        if key:
            values[number]=key[1].strip()
    return values


def english(folder, name):
    yr=int(name[2:])
    spans, key_window=SPANS[name]
    lines=(folder/("en22clean.txt" if name=="en22" else name+".txt")).read_text(encoding="utf8").splitlines()
    if name=="en21":
        lines[264]=lines[264].replace("In his spare on stage","In his spare time though he goes on stage")
    if name=="en20":
        lines[61] = lines[61].replace("D Writing", "D. Writing")
        lines[110] = lines[110].replace("23 A.", "23. A.")
    keyed,grammar=answers(lines,name,key_window)
    actual_offset=0 if yr in (21,22,24,26) else 20
    passages, questions={}, []
    def raw(i):
        left,right=spans[i]
        return clean(lines[left-1:right])
    def add(number,section,kind,points,stem,answer,options=None):
        left,right=spans[section]
        q={"number":number+actual_offset,"source_number":number,"kind":kind,"points":points,"stem":stem,
           "answer":answer,"topic":("阅读理解","阅读理解","阅读理解","阅读理解","七选五","完形填空","语法填空","应用文","读后续写")[section],
           "position":f"题面快照第 {left}–{right} 行；原来源标号 {number}"}
        if section<7:
            q["passage"]=f"reading-{section}"
        if options:
            q["options"]=options
        questions.append(q)
    starts=[21,24,28,32,36,41,56,66,67]
    starts=[n-actual_offset for n in starts]
    for section,n in enumerate(starts[:4]):
        paragraph,items=numbered(raw(section),range(n,starts[section+1]))
        assert len(paragraph)>250,(name,section,len(paragraph))
        passages[f"reading-{section}"]=paragraph
        for num,stem,opts in items:
            add(num,section,"single_choice",2.5,stem,keyed[num],opts)
    paragraph,opts=split_options(raw(4),"ABCDEFG")
    passages["reading-4"]=paragraph
    for num in range(starts[4],starts[5]):
        add(num,4,"single_choice",2.5,f"选择能填入短文第 {num} 号空的句子。",keyed[num],opts)
    paragraph,items=numbered(raw(5),range(starts[5],starts[6]))
    passages["reading-5"]=paragraph
    for num,stem,opts in items:
        add(num,5,"single_choice",1,stem or f"选择能填入短文第 {num} 号空的词语。",keyed[num],opts)
    passages["reading-6"]=raw(6)
    for num in range(starts[6],starts[7]):
        add(num,6,"grammar_gap",1.5,f"填写短文中第 {num} 号空。",grammar[num])
    for section in (7,8):
        raw_text=raw(section)
        assert len(raw_text)>50, "写作题干缺失"
        sample=ENGLISH_WRITINGS[yr][section-7]
        if yr==22:
            original=(folder/"en22-layout.txt").read_text(encoding="utf8").splitlines()
            answer=clean(original[sample[0]-1:sample[1]])
        elif yr==24 and section==8 and (folder/"en24-continuation.txt").is_file():
            answer=(folder/"en24-continuation.txt").read_text(encoding="utf8").strip()
        else:
            answer=clean((folder/"en26alt.txt").read_text(encoding="utf8").splitlines()[sample[0]-1:sample[1]]) if yr==26 else (
            clean(lines[sample[0]-1:sample[1]]) if sample else "")
        if not answer:
            answer="开放作答。该来源缺范文，须依据题干要求评阅。"
        add(starts[section],section,"writing",15 if section==7 else 25,raw_text,answer)
    if yr==25:
        questions[0].update(images=["en25-chart.png"],requires_figure=True,position="源 PDF 第1页图；笔试第1题")
        passages["reading-0"]=passages["reading-0"].replace(
            "different modes of transport.", "different modes of transport.\n"
            "[Chart: Road passengers 45.1%; road goods 29.4%; airplanes 11.6%; "
            "shipping 10.6%; rail 1%; other 2.2%.]",1)
    return {"id":f"20{yr}-cn-english-national-1","subject":"english","year":2000+yr,"regions":ZH_REGIONS[2000+yr],
            "title":f"20{yr} 年全国新高考Ⅰ卷英语（完整笔试）","series_id":"cn-new-gaokao-1",
            "exam_kind":"official_exam","question_count":47,"points":120,"written_only":True,
            "source":{"title":"公开试卷及参考答案转写","url":URLS[name],
                      "answer_url":{22:"https://m.jszs.com/uploads/file/202312/06/1701849185494197.pdf",
                                    24:URLS[name],26:"https://www.sjds.net/a/504250.html"}.get(yr,URLS[name]),
                      "writing_sample_source_url":"https://sjds.net/825768.html" if yr==24 else None,
                      "text_crosscheck_url":"https://www.cpsenglish.com/article/385" if yr==21 else URLS[name]},
            "questions":questions,"passages":passages}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshots",type=Path)
    parser.add_argument("papers",nargs="+",choices=SPANS)
    args=parser.parse_args()
    for name in args.papers:
        try:
            print(name,ingest(ROOT,english(args.snapshots,name),images=args.snapshots,track=True))
        except (AssertionError,ValueError) as error:
            print(name,"校验失败",error)


if __name__=="__main__":
    main()
