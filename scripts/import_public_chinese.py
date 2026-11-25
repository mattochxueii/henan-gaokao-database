"""Normalize saved public page snapshots. Network acquisition is deliberately separate."""
import argparse
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bootstrap  # noqa: F401
from core.paper_intake import ingest
from gaokao import ROOT, require

ZH_REGIONS = {2020: ["山东"], 2021: ["山东", "河北", "江苏", "福建", "湖北", "湖南", "广东"],
              2022: ["山东", "河北", "江苏", "福建", "湖北", "湖南", "广东"],
              2023: ["山东", "河北", "江苏", "福建", "湖北", "湖南", "广东", "浙江"],
              2024: ["河南","山东","河北","江苏","福建","湖北","湖南","广东","浙江","安徽","江西"],
              2025: ["河南","山东","河北","江苏","福建","湖北","湖南","广东","浙江","安徽","江西"],
              2026: ["河南","山东","河北","江苏","福建","湖北","湖南","广东","浙江","安徽","江西"]}

# Transcribed score vectors. Section totals vary independently of the question count.
ZH_SCORES = {
    2020: [3,3,3,4,6,3,3,4,6,3,3,3,8,3,3,6,6,3,4,4,4,5,60],
    2021: [3,3,3,4,6,3,3,4,6,3,3,3,8,3,3,6,6,3,3,5,3,6,60],
    2022: [3,3,3,4,4,3,3,6,6,3,3,3,8,3,3,6,6,3,4,4,3,6,60],
    2023: [3,3,3,4,6,3,3,4,6,3,3,3,8,3,3,6,6,4,6,3,4,3,60],
    2024: [3,3,3,4,6,3,3,4,6,3,3,3,8,5,3,6,6,5,2,4,4,3,60],
    2025: [3,3,3,4,6,3,3,4,6,3,3,3,8,5,3,6,6,4,3,3,4,4,60],
    2026: [3,3,3,4,6,3,3,6,8,3,3,3,8,3,3,6,6,4,3,4,5,60],
}
SLUG = {2020:"gaokao-chinese-2020-shandong", 2021:"gaokao-chinese-2021-shandong",
        **{y:f"gaokao-chinese-{y}-i" for y in range(2022,2027)}}
FIGURES = {(2025,21): ["z25-21a.png","z25-21b.png"]}


def body(node):
    if node is None:
        return ""
    for br in node.select("br"):
        br.replace_with("\n")
    for tag in node.select("u, strong, em, sub, sup"):
        value=tag.get_text()
        tag.replace_with(f"<{tag.name}>{value}</{tag.name}>")
    return "\n".join(line.strip() for line in node.get_text("\n",strip=True).splitlines() if line.strip())


def zh_topic(number, last):
    for end,topic in ((5,"信息类阅读"),(9,"文学类阅读"),(14,"文言文阅读"),
                      (16,"古代诗歌"),(17,"名篇名句默写"),(last-1,"语言文字运用"),(last,"写作")):
        if number <= end:
            return topic


def chinese(folder, year):
    name = f"l{year%100:02d}"
    base = f"https://liangshibao.com/tiku/{SLUG[year]}"
    index = BeautifulSoup((folder/(name+".html")).read_bytes(),"html.parser")
    passages, questions = {}, []
    for section_i, section in enumerate(index.select(".paper-section"),1):
        passage_id=f"material-{section_i}"
        text=body(section.select_one(".material-panel"))
        if text:
            passages[passage_id]=text
        for link in section.select(".card-grid a[href]"):
            tail=link["href"].rsplit("/",1)[-1]
            source=folder/f"{name}-{tail}.html"
            detail=BeautifulSoup(source.read_bytes(),"html.parser").select_one("article.detail-card")
            require(detail is not None, "缺公开题目内容："+str(source))
            number=int(tail.rsplit("-",1)[-1])
            stem=body(detail.select_one(".question-stem"))
            options={opt.select_one(".question-option-key").get_text(strip=True):body(opt.find_all("span",recursive=False)[-1])
                     for opt in detail.select(".question-option")}
            answer=body(detail.select_one(".question-answer"))
            analysis=body(detail.select_one(".question-analysis"))
            kind="single_choice" if len(options)==4 and answer in options else "response"
            q={"number":number,"stem":stem,"answer":answer,"explanation":analysis or None,"options":options,
               "kind":kind,"points":ZH_SCORES[year][number-1],"position":urljoin(base,link["href"]),
               "topic":zh_topic(number,len(ZH_SCORES[year]))}
            if text and number!=17:
                q["passage"]=passage_id
            if (year,number) in FIGURES:
                q["requires_figure"]=True
                q["images"]=FIGURES[year,number]
                q["figure_source_url"]="https://www.gengyun.org.cn/news/yuwentiandi/2025/8103.html"
            questions.append(q)
    questions.sort(key=lambda q:q["number"])
    require(len(questions)==len(ZH_SCORES[year]),"语文题数不足")
    require(sum(ZH_SCORES[year])==150,"语文总分异常")
    return {"id":f"{year}-cn-chinese-national-1","subject":"chinese","year":year,"regions":ZH_REGIONS[year],
            "title":index.select_one("h1.page-title").get_text(strip=True),"series_id":"cn-new-gaokao-1",
            "exam_kind":"official_exam","question_count":len(questions),"points":150,
            "source":{"title":"良师宝公开逐题转录与参考解析","url":base,"authority":"public_transcription"},
            "passages":passages,"questions":questions}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshots",type=Path)
    parser.add_argument("year",type=int,nargs="+",choices=ZH_SCORES)
    args=parser.parse_args()
    for year in args.year:
        print(year,ingest(ROOT,chinese(args.snapshots,year),images=args.snapshots,track=True))


if __name__=="__main__":
    main()
