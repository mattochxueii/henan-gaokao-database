"""Create separate student and post-exam packets from a certified original paper."""

import argparse
import csv
from pathlib import Path
import shutil
from zipfile import ZIP_DEFLATED, ZipFile

from gaokao import digest, dumps, read_json, require
from student_feedback import checked_questions, make_csv, paper_layout


def record_sheet(path, paper_id, scores, minutes):
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.lib.colors import HexColor
    from mathgen.export import chinese_font

    page = canvas.Canvas(str(path), pagesize=A4, invariant=True)
    font = chinese_font()
    page.setTitle(paper_id + " 匿名试做记录")
    page.setFont(font, 17)
    page.drawString(48, 792, "数学试做  ·  匿名记录表")
    page.setFont(font, 10)
    page.drawString(48, 768, f"{paper_id}  |  建议限时 {minutes} 分钟  |  匿名代码 __________________")
    page.drawString(48, 749, "作答时只记用时。先交卷或封存答案，再按独立评分细则登记得分。")
    page.drawString(48, 733, "重复返回一道题时累计用时。没完成与没记录分别标记，避免填入姓名或学校。")
    top = 711
    left, right, height = 48, 547, 23
    headings = [("题号",58),("满分",105),("用时（秒）",152),("自评得分",238),
                ("状态",309),("主要困难与错误",377)]
    page.setFillColor(HexColor("#eef2f6"))
    page.rect(left,top-height,right-left,height,stroke=0,fill=1)
    page.setFillColor(HexColor("#142334"))
    for label,x in headings:
        page.drawString(x,top-15,label)
    page.setStrokeColor(HexColor("#98a4b2"))
    for index, score in enumerate(scores,1):
        y = top - (index+1)*height
        page.line(left,y,right,y)
        page.drawString(60,y+8,str(index))
        page.drawString(108,y+8,str(score))
    end = top - (len(scores)+1)*height
    page.setFont(font,9)
    page.drawString(left,end-25,"状态可写「全对、部分得分、错误、未完成」。未记录留空。")
    page.drawString(left,end-41,"困难可记「概念、建模、计算、推理、读题、时间」。完整反馈请用随包 CSV。")
    page.save()


def make_kit(paper, output, *, scoring_notes=None):
    cert = read_json(paper/"publication.json")
    paper_sha, points = checked_questions(paper)
    paper_id, numbers = paper_layout(paper)
    minutes = read_json(paper/"student-text.json")["minutes"]
    require(len(numbers) == 19 and sum(points.values()) == 150, "试做包要求已审核的19题150分试卷")
    output.mkdir(parents=True, exist_ok=False)
    before, after = output/"student", output/"after"
    before.mkdir()
    after.mkdir()
    shutil.copyfile(paper/"paper.pdf",before/"paper.pdf")
    shutil.copyfile(paper/"solutions.pdf",after/"solutions.pdf")
    if scoring_notes is not None:
        shutil.copyfile(scoring_notes,after/"scoring-notes.md")
    record_sheet(before/"record-sheet.pdf",paper_id,[points[qid] for qid in numbers.values()],minutes)
    make_csv(after/"feedback-blank.csv",paper_id,paper_sha,numbers,extended=True)
    with (after/"teacher-review-blank.csv").open("x",encoding="utf-8-sig",newline="") as handle:
        fields = ("paper_sha256", "number", "question_id", "math_issue", "wording_issue",
                  "scoring_issue", "curriculum_scope_issue", "position_demand_note", "evidence")
        writer = csv.DictWriter(handle,fieldnames=fields)
        writer.writeheader()
        for number, qid in numbers.items():
            writer.writerow({"paper_sha256":paper_sha,"number":number,"question_id":qid})
    (before/"READ-ME.txt").write_text(
        f"{paper_id}\n限时 {minutes} 分钟。打开 paper.pdf，打印或抄录 record-sheet.pdf。\n"
        "从开始读题起记录单题用时，回看时累计。先保存作答与用时，再索取评分包。\n"
        "未做完可以记实际得分，未记录保持空白。匿名代码可临时随机生成，勿写姓名或学校。\n",
        encoding="utf-8",
    )
    (after/"READ-ME.txt").write_text(
        f"{paper_id}，请在作答结束后打开。\n"
        "solutions.pdf 含解法及项目评分步骤。对照逐项赋分，填写 feedback-blank.csv。\n"
        "participant_code 使用4到32位随机英数字、下划线或连字符。整行无反馈则跳过。\n"
        "seconds 为整数秒，score 为实际得分，status 用 correct、partial、incorrect、unfinished。\n"
        "error_types 用 concept、model、calculation、logic、reading、time 或 other，多个用 | 分开。\n"
        "reading_difficulty、reasoning_load、calculation_load 为0到3，表示无到高。\n"
        "explanation_clarity 为0到3，表示完全不清楚到清楚。ambiguity_reported、scoring_issue 填0或1。\n"
        "method_note 可写解题或评分分歧，请勿写任何个人身份信息。保留原列名及绑定字段。\n"
        "在项目根目录运行，<试卷目录> 指含原 publication.json 的 HN9-M150-v1 目录。\n"
        "python scripts/student_feedback.py <试卷目录> prepare feedback-blank.csv work/trial.json\n"
        "python scripts/student_feedback.py <试卷目录> diagnose work/trial.json <匿名代码>\n"
        "python scripts/student_feedback.py <试卷目录> summary work/trial.json\n"
        "教师可提交实际审阅结果，逐题记录步骤、可能分歧、依据和试卷哈希。教师审阅为自愿。\n",
        encoding="utf-8",
    )
    for folder, archive_name in ((before,"student-before.zip"),(after,"scoring-after.zip")):
        with ZipFile(output/archive_name,"x",ZIP_DEFLATED) as archive:
            for file in sorted(folder.iterdir()):
                archive.write(file,file.name)
    manifest = {
        "paper_id":paper_id,"paper_sha256":paper_sha,"solutions_sha256":cert["solutions_sha256"],
        "minutes":minutes,"questions":len(points),"points":sum(points.values()),
        "teacher_reviews":0,"real_student_trials":0,
        "artifacts":{f.name:digest(f) for f in sorted(output.glob("*.zip"))},
    }
    (output/"manifest.json").write_text(dumps(manifest)+"\n",encoding="utf-8")
    return manifest


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("paper",type=Path)
    p.add_argument("output",type=Path)
    p.add_argument("--scoring-notes",type=Path)
    args = p.parse_args()
    print(dumps(make_kit(args.paper,args.output,scoring_notes=args.scoring_notes)))


if __name__ == "__main__":
    main()
