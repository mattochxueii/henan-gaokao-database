"""Create the Phase 23 preregistration from checked archive records and dated sources."""
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[3]
SOURCE=Path(__file__).parent
sys.path.insert(0,str(ROOT/"scripts"))
import bootstrap
from forecast_store import write_new
from gaokao import digest, read_json, require
from math_trends import LOCKED_FILES, SIGNALS, SNAPSHOT, V3, V3_SHA256, validate_snapshot


def main():
    bank=ROOT/SIGNALS
    evidence=read_json(bank/"evidence.json")
    notes=read_json(SOURCE/"position-notes.json")
    papers=[]
    for source in evidence["sources"]:
        if source["id"] not in notes:
            continue
        comments=notes[source["id"]]
        require(len(comments)==19,"对照笔记必须有实际的19题")
        doc=read_json(ROOT/source["archive"]) if source.get("archive") else None
        positions=[]
        for number,comment in enumerate(comments,1):
            module, action=comment.split("｜",1)
            q=doc["questions"][number-1] if doc else None
            require(not q or q["number"]==number, "正式卷题号错配")
            page=1 if number<=8 else 2 if number<=13 else 3 if number<=17 else 4
            locator=(q.get("position") or f"档案第{number}题") if q else (
                f"卷面第{number}题" if source["year"]==2024 else f"印刷页{page}第{number}题")
            positions.append({
                "number":number, "question_id":q["id"] if q else f"{source['id']}:q{number:03d}",
                "version_sha256":q["version_sha256"] if q else None, "locator":locator,
                "scope":("practice_text" if q["usable_for_practice"] else "limited_position_evidence")
                if q else "public_printed_question",
                "module":module,"action":action,
            })
        papers.append({"source":source["id"],"exam_kind":source["type"],"year":source["year"],
                       "source_url":source.get("content_url",source["url"]),"positions":positions})
    compare={"version":"math-19-position-comparison-v1","observation_count":sum(len(p["positions"]) for p in papers),
             "papers":papers,"notes":[
                 "三份正式卷与两份适应性测试分别观察。演练仅用于设计外壳与解题动作对照。",
                 "2024全国Ⅰ卷用于同系列比较，非河南当年正式数学卷。",
                 "2026档案第9、12、18题仅用于已确认题位和模块观察；不据存疑选项推导结论。",
                 "题位是同一试卷内的组成部分，95条记录不是95份独立样本。",
             ]}
    require(not (ROOT/SNAPSHOT).exists(), "已有冻结文件，修订须另版")
    require(digest(ROOT/V3)==V3_SHA256,"旧v3已改变")
    write_new(bank/"position-comparison.json",compare)
    snapshot={
        "version":"henan-2027-math-trends-v1","kind":"prospective_qualitative_registration",
        "cutoff":"2026-11-23","registered_on":"2026-11-23",
        "target":{"year":2027,"subject":"math","region":"河南","series":"cn-new-gaokao-1","papers":"official_exam"},
        "eligibility":"仅在河南2027实际使用全国Ⅰ卷且沿用19题制时按原题位验收。若发生改制，记录不适用。",
        "freeze_scope":"私有仓库考前文件与哈希。无第三方时间戳，另版修订不覆盖此文件。",
        "evidence_policy":"强证据描述官方方向及多份正式卷交叉支持。有限观察为少量样本的可证伪假说。证据不足保留弃权。",
        "evaluation":"真题公布后按原题号和布尔标记登记。每次命中带来源位置与数学理由。弃权不进结果统计。",
        "v3_sha256":V3_SHA256,"inputs":{n:digest(bank/n) for n in LOCKED_FILES},
        "entries":read_json(SOURCE/"trend-proposals.json"),
    }
    write_new(ROOT/SNAPSHOT,snapshot)
    validate_snapshot(ROOT)
    print(digest(ROOT/SNAPSHOT))


if __name__=="__main__":
    main()
