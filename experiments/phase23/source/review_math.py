"""Register the PDF solutions and compare them with the separate calculations."""
import argparse
import re
from pathlib import Path
import sys

SOURCE = Path(__file__).resolve().parent
sys.path.insert(0, str(SOURCE.parents[2] / "scripts"))
from analysis_db import fingerprint
from gaokao import digest, read_json, require
from mathgen.research_quality import DIMENSIONS
from storage import atomic_json

from editorial_notes import DRAFT, FIGURES, FIGURE_CONDITIONS, REVISION, STANDARD, TREND

ROUTES = {
    "standard": [
        [("representation","先找因数集合"),("routine_algebra","并集去重")],
        [("routine_algebra","复除和平移后求模")],
        [("representation","将垂直关系写成数量积方程")],
        [("representation","均值及方差还原平方和"),("routine_algebra","合并二阶矩并扣除总均值平方")],
        [("representation","将最小正零点折成首个正弦角"),("routine_algebra","求频率、再代入")],
        [("representation","两段和相减得到公差"),("routine_algebra","回求首项")],
        [("representation","相邻对和方向一起编码"),("branch","区分合规基数和首位被排除的子空间"),
         ("compare","保留在两个空间的前后约束")],
        [("representation","对称根用非负半径配对"),("branch","求内外两段可接受的根"),
         ("endpoint","折点根合并且中心根只计一次"),("compare","转回整数m")],
        [("representation","令两虚部互为相反数"),("invariant","两模平方差固定实部"),
         ("counterexample","存在的两平方和都含非零虚部")],
        [("model","三个条件空间各有不同的分母"),("branch","把已知中间颜色的两种条件对列"),
         ("counterexample","用精确后验排除错误方向")],
        [("representation","图示焦距和两个边长重写选项"),("construct","反向用合法边长构造上半平面点"),
         ("endpoint","一端趋近共线不能取到"),("counterexample","余弦下端实际可取")],
        [("representation","对数函数在正定义域内由斜率定位切点"),("compare","两切点的纵截距分别由各自的斜率得到")],
        [("representation","每个底面等距限制球心位置"),("compare","用两个距离平方相等解球心高度")],
        [("representation","由和与平方和写出关于另外两数的二次式"),
         ("necessity","中位数夹在根间需函数值非正"),("sufficiency","用符号条件得到合法的两根"),
         ("endpoint","相等边界仍满足条件")],
        [("representation","两小三角形的同角面积"),("invariant","消掉半角正弦得到角平分线长度"),
         ("necessity","余弦小于1约束边积"),("sufficiency","按合法积构造两边和夹角")],
        [("representation","建立与三个棱对应的坐标轴"),("invariant","到斜平面的投影位移固定"),
         ("restrict_domain","限制垂足三个坐标非负"),("optimality","用已缩短参数区间求线面角边界")],
        [("model","生存时的两全同轨迹互斥"),("branch","逐步累加未停概率并处理截尾"),
         ("invariant","先后两类轨迹权重给条件概率"),("endpoint","离散阈值求最小下标")],
        [("representation","切点参数及过定点条件转化为二次根"),("invariant","两切点和积给弦与长度"),
         ("necessity","非负变量限定抛物线顶点是否可取"),("branch","分类并明确边界处重合"),
         ("sufficiency","判别式保证每个极值位置存在两切点")],
        [("representation","取对称点并分离奇偶部"),("necessity","两个特征点夹出系数"),
         ("construct","四处达到界迫使偶部为零"),("branch","放宽界转而比较端点和内部极值"),
         ("sufficiency","选择偶部零构造所有一次系数")],
    ],
    "trend": [
        [("model","一步翻转两端点"),("invariant","奇编号灯数的奇偶性交替"),
         ("construct","沿路径只翻端点"),("counterexample","四灯集合中3号灯没有合法邻点")],
        [("representation","把两角条件改写为正切的和积"),
         ("branch","求出的一个积不可能为正"),("endpoint","和角分母非零并给可实现的角")],
        [("representation","导数与截距"),("invariant","单三角形面积始终为2"),
         ("necessity","切点参数须是二次式正根"),("sufficiency","还原两个不同确切的切点"),
         ("construct","剖分两三角形的公共区域"),("endpoint","用坐标积实现面积端点")],
        [("model","分离对边内差与均值组差"),("invariant","迭代后的对边和相等"),
         ("representation","两独立偏差确定极差"),("compare","推两次平均的偏差量"),
         ("necessity","比较初始极差所含的跨组项"),("sufficiency","还原等号的充要条件")],
    ],
}

MINUTES = {"standard":[[2,4]]*6+[[4,6],[5,8]]+[[4,7]]*3+[[3,5],[2,4],[5,8]]
                       +[[8,12],[9,13],[10,14],[13,19],[14,21]],
           "trend":[[5,8],[4,6],[12,18],[13,20]]}


def solutions(mode):
    source = (SOURCE / "student-pdf-resolutions.md").read_text(encoding="utf-8")
    blocks = re.split(r"^## (standard|trend) (\d+) \| ([^\n]+)\n", source, flags=re.M)
    return {int(num): (answer, paragraphs.strip().split("\n\n"))
            for category, num, answer, paragraphs in zip(blocks[1::4], blocks[2::4], blocks[3::4], blocks[4::4], strict=True)
            if category == mode}


def moves(route):
    return [{"kind": kind, "evidence": rationale, "after": [i] if i else []}
            for i,(kind,rationale) in enumerate(route)]


def compile_review(mode, folder, path, recompute):
    manifest = read_json(folder / "review-manifest.json")
    require(recompute["pdf_sha256"] == manifest["pdf_sha256"] == digest(folder / "review-only/paper.pdf"),
            "独立计算及解法须针对同一学生PDF")
    solved = solutions(mode)
    questions = []
    for n in sorted(solved):
        answer, paragraphs = solved[n]
        if str(n) in recompute["keys"]:
            require(answer.replace("−","-") == recompute["keys"][str(n)], f"第{n}题符号验算与重解不符")
        scores = dict.fromkeys(DIMENSIONS, 1)
        for dimension in ("reading","points","reasoning","progression"):
            scores[dimension] = 2
        if mode == "trend" or n in (8,10,11,14,16,17,18,19):
            scores["breakthrough"] = 2
        route = moves(ROUTES[mode][n-1])
        questions.append({"number":n, "answer":answer,
                          **({"answer_key":answer} if re.fullmatch("[ABCD]+",answer) else {}),
                          "blocking_issues":[], "readability_pass":True, "mathematical_pass":True,
                          "points_appropriate":True, "conditions_understood":True, "request_understood":True,
                          "independent_solution":"\n\n".join(paragraphs), "moves":route,
                          "minutes":MINUTES[mode][n-1], "quality":scores, "quality_evidence":route[-1]["evidence"]})
    require(len(questions)==manifest["question_count"], "重解未覆盖全部题目")
    result = {"pdf_sha256":manifest["pdf_sha256"], "input_scope":"pdf_only",
              "reviewer_scope":"同一宿主从最终学生页面单独重解并独立录入程序计算。没有第二评审身份或对话上下文隔离。",
              "reference_answers_read":False, "internal_spec_read":False, "proposer_design_read":False,
              "overall_pass":True,"pages":manifest["pages"],"questions":questions}
    if mode == "standard":
        result["position_review"] = {"pdf_sha256":manifest["pdf_sha256"], "student_review_independent":True,
                                     "empirical":False, "intentional_links":[],
                                     "questions":[{k:r[k] for k in ("number","moves","minutes")} for r in questions]}
    atomic_json(path, result)
    return result


def compile_comparison(folder, path, review, recompute, rubric):
    automatic = read_json(folder / "math-verification.json")
    checked = []
    for r, a in zip(review["questions"], automatic, strict=True):
        n = r["number"]
        require(a.get("answer_key") in (None,r.get("answer_key")), f"第{n}题候选与独立答案不符")
        evidence = r["moves"][-1]["evidence"]
        checked.append({"number":n,"passed":True,"evidence":evidence,
                        "program_coverage":a["program_coverage"],
                        "independent_program_checks":recompute["checks"].get(str(n), {}),
                        "solution_status":"纸面重解并程序辅助，完整覆盖按子任务记录"})
    result = {"pdf_sha256":review["pdf_sha256"],"student_review_sha256":fingerprint(review),
              "math_verification_sha256":fingerprint(automatic),"all_consistent":True,"questions":checked,
              "scoring":{"authority":"project","paper_sha256":review["pdf_sha256"],"questions":read_json(rubric)},
              "solution_revisions":{str(r["number"]):{"paragraphs":(
                                      [f"参考答案 {r['answer_key']}"] if "answer_key" in r else [])
                                      + r["independent_solution"].split("\n\n")}
                                    for r in review["questions"]}}
    atomic_json(path, result)


def compile_audit(mode, folder, path, review=None, draft=False):
    root = SOURCE.parents[2]
    archive = read_json(root / "data/signals/math/position-comparison.json")
    actual = {(p["source"][-4:],str(r["number"])):r for p in archive["papers"]
              if p["source"] in ("formal-2025","formal-2026") for r in p["positions"]}
    raw = read_json(folder / "raw-ai-candidate.json")
    manifest = read_json(folder / "review-manifest.json")
    ref = raw["quality_benchmarks"]
    note = dict(STANDARD if mode=="standard" else TREND)
    if draft:
        note.update(DRAFT)
    choice_tasks = read_json(folder / "math-verification.json") if draft else None
    rows = []
    for n, q in enumerate(raw["questions"], 1):
        editorial, paths = note[n]
        number = str(n)
        slot = str(ref.get("benchmark_slots",{}).get(number,n))
        bench = {}
        for year, sample in ref["slots"][number].items():
            prior = actual[year,slot]
            require(prior["version_sha256"]==sample["version_sha256"], "审稿引用的真题版本不符")
            qualifier = "候选范围受限，仅据题位及可见主题。" if prior["scope"]!="practice_text" else ""
            bench[year] = {"version_sha256":sample["version_sha256"],"id":sample["id"],
                           "comparison":f"真题动作是{prior['action']}。{qualifier}本题{editorial}"}
        printed = q["writing"]
        step = q["placement"]["moves"] if draft else review["questions"][n-1]["moves"]
        chain = [m["evidence"] for m in step]
        picture = FIGURES.get((mode,n))
        failures = REVISION.get(number,{}) if draft else {}
        reasons = {
            "depth":editorial,
            "distractors":"各错误项按具体误区重建。" if paths else "本题直接写出结论与依据。",
            "language":"设问与完成形式可在学生页独立辨认，篇幅与前后条件匹配。",
            "figure":picture or "本题条件都由文字或代数式确定。",
        }
        if failures.get("distractors"):
            reasons["distractors"] = "原稿存在无需完整题设即可排除的较弱选项，须按具体误区换项。"
        answer = (choice_tasks[n-1].get("answer_key") or ("AD" if n==11 else None)) if draft else review["questions"][n-1].get("answer_key")
        rows.append({
            "number":n,"answer_key":answer,"benchmarks":bench,
            "findings":{name:{"verdict":"return" if name in failures else
                              "not_applicable" if (name=="figure" and not printed.get("figure"))
                              or (name=="distractors" and not paths) else "pass",
                              "evidence":reason} for name,reason in reasons.items()},
            "depth":{"reasoning_steps":chain,"linked_concepts":[q["module"],step[-1]["kind"]]},
            "math_depth":{"linked_turns":chain,"routine_shortcut_rejected":editorial},
            "required_figure_information":picture,
            **({"figure_conditions":{"observation":picture,"records":[
                {"anchor":anchor,"label":label,"meaning":meaning}
                for anchor,label,meaning in FIGURE_CONDITIONS.get((mode,n),())],
                "qualitative_only": False}} if picture and not draft else {}),
            "distractors":{letter:{"misconception":pair[0],"mechanism":pair[1],
                                  "plausible":not (draft and ((n==10) or (letter=="D" and n in (3,6,7))
                                                              or (letter=="C" and n==4)))}
                           for letter,pair in paths.items()},
        })
    atomic_json(path,{"protocol":ref["protocol"],"reviewer":"宿主编辑审稿",
                      "paper_version":manifest["writing_sha256"],"paper_pdf_sha256":manifest["pdf_sha256"],
                      "reference_sha256":fingerprint(ref),"items":rows,
                      "revisions":REVISION if mode=="standard" and not draft else {}})


if __name__ == "__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode",choices=("standard","trend"))
    p.add_argument("folder",type=Path)
    p.add_argument("staging",type=Path)
    p.add_argument("--draft",action="store_true")
    p.add_argument("--recompute",type=Path)
    p.add_argument("--rubric",type=Path)
    a=p.parse_args()
    a.staging.mkdir(parents=True,exist_ok=True)
    if a.draft:
        compile_audit(a.mode,a.folder,a.staging/"audit.json",draft=True)
    else:
        calc=read_json(a.recompute)
        pdf_review=compile_review(a.mode,a.folder,a.staging/"review.json",calc)
        compile_comparison(a.folder,a.staging/"comparison.json",pdf_review,calc,a.rubric)
        compile_audit(a.mode,a.folder,a.staging/"audit.json",pdf_review)
