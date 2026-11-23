"""Check reviewed, rendered paper metrics and publish the Phase 22 records."""
import argparse
from pathlib import Path
from shutil import copyfile
import subprocess
import sys

from PIL import Image
from pypdf import PdfReader

SOURCE = Path(__file__).resolve().parent
ROOT = SOURCE.parents[2]
sys.path[:0] = [str(ROOT / "scripts"),str(SOURCE.parents[1] / "phase21" / "source")]
from core.science_workflow import blank_numbers, check_publication
from gaokao import digest, read_json
from record_review import printed_questions
from storage import atomic_json

VISUAL = {
    "physics": {
        "student": [
            "首节和 Q1–4。核对两行亮纹共用刻度、速度图量纲、临界光线位置。",
            "Q5–7。检查四幅图同标度、正负台阶和时刻、甲乙衰减曲线、P 点载荷和尺寸。",
            "Q8–10。多选说明只出现一次，节点与轴标完整，定差题选项左右成对换行。",
            "Q11–13。查光电门与弹簧不穿过滑块，电表串并联正确，11 处横线完整，电子束图两段 L 对齐。",
            "Q14–15。外气室开口与弹簧间隙可读，粗糙区 O 到 P、弹簧固定端、所有计算问在末页。",
        ],
        "answers": [
            "核对 Q1–11 的逐项判断、物理量单位和公式，Q12 的圈号答案在页尾。",
            "Q12 从推导开始续排，Q13–15 完整，核对严格临界的根式和全部评分条目。",
        ],
        "choice_figures":[2,3,4,5,6,7,8,10],
    },
    "chemistry": {
        "student": [
            "Q1–3。氮化硼原子点与化学键清晰，3.10/20.40 mL 的凹面窗及尖嘴分开。",
            "Q4–7。流程箭头、钙镁柱高、有机键线式与独立列出的长离子方程清晰。",
            "Q8–11。能垒图例与数据点无重叠，膜边界连续，分布交点与晶胞四层分数刻度可辨。",
            "Q12–14。热重平台、标记碳及两条沉淀共存线与正确题号相配，双列长项同排续行。",
            "Q15–16。锂母液回用分支、测量表及放大横线完整，铝镁初始浓度清楚。",
            "Q17–18。分行的耦合反应、选择性柱高、合成六步不与结构标签相连，末问长横线和分值完整。",
        ],
        "answers": [
            "逐项核对 Q1–13：化学式、电荷上标、图上读数和碱处理前后口径。",
            "Q14–17：检查沉淀阈值、两条反应方程式、四道大题中的前三道圈号答案及评分续排。",
            "Q17 末评分续接，Q18 六步、20 种、四步路线的答案及评分齐全。",
        ],
        "choice_figures":[2,3,4,6,7,8,9,10,11,12,13,14],
    },
    "legacy": {
        "student": [
            "旧卷第 1 页单选的长选项成对换行。",
            "旧卷第 2 页第8题波形图纵轴标签离纸面充足，刻度和图题不重叠。",
            "旧卷第 3 页检查 Q9–11 的电路与门位。",
            "旧卷第 4 页核对 Q12–14 的横线和装置。",
            "旧卷第 5 页第15题示意图及三个子问完整。",
        ],
        "answers": [
            "旧卷第 1 页核对 Q1–11 及 Q12 的圈号和电源测量关系。",
            "旧卷第 2 页核对运动边界、根式、热学数值及评分。",
        ],
        "choice_figures":[3,4,5,6,8,9,10],
    },
}


def rules_count(document):
    lengths = []
    for page in document.pages:
        width = start = None
        stack = []
        for args, op in page.get_contents().operations:
            if op == b"q":
                stack.append(width)
            elif op == b"Q":
                width = stack.pop()
            elif op == b"w":
                width = float(args[0])
            elif op == b"m":
                start = [float(v) for v in args]
            elif op == b"l" and width == .65:
                x,y = map(float,args)
                assert abs(y-start[1]) < .0001
                lengths.append(x-start[0])
            elif op == b"S":
                start = None
    return lengths


def command(*args, expected=0):
    result = subprocess.run(
        [sys.executable,"-X","utf8",str(ROOT/"scripts/gaokao_platform.py"),*map(str,args)],
        cwd=ROOT,capture_output=True,text=True,encoding="utf8",
    )
    if result.returncode != expected:
        raise RuntimeError(result.stdout+result.stderr)
    return result


def check_rendered(folder, subject):
    packet=read_json(folder/"blind-packet.json")
    paper=packet["paper"]
    questions=paper["questions"]
    visual=VISUAL[subject]
    docs=[PdfReader(folder/f"{name}.pdf") for name in ("paper","solutions")]
    expected=[(q["order"],None if q["options"] else q["points"]) for q in questions]
    for doc,pages in zip(docs,[visual["student"],visual["answers"]],strict=True):
        texts=[p.extract_text() for p in doc.pages]
        assert len(texts)==len(pages) and all(len(t.strip())>200 for t in texts)
        assert printed_questions(texts)==expected
    assert sum(q["points"] for q in questions) == paper["total_points"] == 100
    assert paper["minutes"] == 75
    student="".join("".join(p.extract_text().split()) for p in docs[0].pages)
    assert "参考答案与解析" not in student and "项目参考评分" not in student
    assert student.count("选对但不全得3分")==int(subject!="chemistry")
    figures=[q["order"] for q in questions if q["options"] and q["figure"]]
    assert figures==visual["choice_figures"]
    specs=[q["figure"] for q in questions if q["figure"]]
    for figure in specs:
        assert digest(folder/figure["path"])==figure["sha256"]
        with Image.open(folder/figure["path"]) as picture:
            assert picture.width>=2000 and picture.height>=500
    blanks={q["order"]:len(blank_numbers(q)) for q in questions if blank_numbers(q)}
    physical_duplex=rules_count(docs[0])
    assert len(physical_duplex)==sum(blanks.values()) and min(physical_duplex)>25
    assert list(blanks)==([15,16,17,18] if subject=="chemistry" else [11,12])
    review=read_json(folder/"independent-review.json")
    assert review["paper_pdf_sha256"]==digest(folder/"paper.pdf")
    assert all(len(row.get("blank_answers",{}))==blanks.get(q["order"],0)
               for q,row in zip(questions,review["items"],strict=True))
    return specs,{
        "paper_version":packet["paper_version"],"reviewer":"Work 宿主逐页目视","passed":True,
        "paper_sha256":digest(folder/"paper.pdf"),"solutions_sha256":digest(folder/"solutions.pdf"),
        "paper_pages":len(docs[0].pages),"solutions_pages":len(docs[1].pages),
        "paper_note":"逐页见 page_checks.paper。","solutions_note":"逐页见 page_checks.solutions。",
        "page_checks":{"paper":visual["student"],"solutions":visual["answers"]},
        "method":"Poppler 145–160 dpi 逐页目视。另核对渲染 PDF 题号、分值及横线笔画。",
        "choice_figure_numbers":figures,"blank_counts_by_question":blanks,
        "measured_continuous_rules":len(physical_duplex),
    }


def publish(subject, work):
    folder=work/f"{subject}-release"
    figures,visual=check_rendered(folder,subject)
    visual_path=work/f"{subject}-visual.json"
    atomic_json(visual_path,visual)
    evidence={}
    if subject!="legacy":
        before=command("publish",folder,visual_path,expected=1)
        assert "缺 quality-audit.json" in before.stderr
        draft=work/f"{subject}-draft"
        review_path=work/f"{subject}-editorial.json"
        command("quality-audit",folder,review_path,"--previous-rejection",draft/"quality-result.json")
        audit=read_json(folder/"quality-audit.json")
        result=read_json(folder/"quality-result.json")
        assert result["status"]=="accepted" and not result["failures"]
        assert sum(len(q["distractors"]) for q in audit["items"]) == (42 if subject=="chemistry" else 27)
        calculations=read_json(folder/"calculation-audit.json")
        assert calculations["paper_sha256"]==visual["paper_sha256"]
        evidence.update({
            "gate_without_audit":{"exit_code":1,"message":before.stderr.strip()},
            "actual_draft_rejection":sorted({row["number"] for row in read_json(draft/"quality-result.json")["failures"]}),
            "new_paper_editorial_acceptance":result["status"],
            "teacher_reviews_received":0,"student_attempts_received":0,
        })
    else:
        dest=ROOT/"experiments/phase21/physics"
        old=read_json(dest/"publication.json")
        evidence.update(previous_paper_sha256=old["visual"]["paper_sha256"],
                        previous_solutions_sha256=old["visual"]["solutions_sha256"],reissued_question_figure=[8])
        calculations=read_json(dest/"calculation-audit.json")
        assert visual["paper_sha256"] != calculations["paper_sha256"]
        calculations={**calculations,"checked_prior_pdf_sha256":calculations["paper_sha256"],
                      "paper_sha256":visual["paper_sha256"],"layout_only_rebind":True}
        atomic_json(folder/"calculation-audit.json",calculations)

    command("publish",folder,visual_path)
    result=read_json(folder/"publication.json")
    check_publication(folder,result)
    dest=ROOT/("experiments/phase21/physics" if subject=="legacy" else f"experiments/phase22/{subject}")
    if subject!="legacy":
        dest.mkdir(parents=True,exist_ok=False)
    (dest/"figures").mkdir(exist_ok=True)
    for filename in (
        "paper.pdf","paper.md","solutions.pdf","solutions.md","publication.json","blind-packet.json",
        "verification.json","independent-review.json","visual-pending.json","calculation-audit.json"
    ):
        copyfile(folder/filename,dest/filename)
    if subject!="legacy":
        for filename in ("quality-audit.json","quality-result.json","draft-quality-rejection.json"):
            copyfile(folder/filename,dest/filename)
        copyfile(draft/"quality-audit.json",dest/"draft-quality-audit.json")
        copyfile(draft/"blind-packet.json",dest/"draft-blind-packet.json")
        copyfile(work/f"{subject}-input"/"draft.json",dest/"draft-ai-candidate.json")
        copyfile(work/f"{subject}-input"/"final.json",dest/"ai-candidate.json")
    else:
        lock=read_json(dest/"reference-lock.json")
        lock["candidate_sha256"]=read_json(folder/"verification.json")["candidate_sha256"]
        atomic_json(dest/"reference-lock.json",lock)
    for fig in figures:
        copyfile(folder/fig["path"],dest/fig["path"])
    atomic_json(dest/("phase22-layout-update.json" if subject=="legacy" else "delivery-check.json"),evidence)
    check_publication(dest,result)
    print(subject,visual["paper_pages"],visual["solutions_pages"],visual["choice_figure_numbers"],
          visual["blank_counts_by_question"])


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("subject",choices=tuple(VISUAL))
    parser.add_argument("work",type=Path,default=ROOT/"work/phase22",nargs="?")
    args=parser.parse_args()
    publish(args.subject,args.work.resolve())
