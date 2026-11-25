"""Regressions taken from the released workbooks and both exam usage modes."""
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import bootstrap
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
from core import exam_qa
from core.review_board import normalize_gap
from gaokao import ROOT, digest
from mathgen.student_pdf import answer_height


def questions(choice, total):
    return [{"kind":"single_choice" if n<=choice else "constructed_response",
             "stem":"阅读数据并作答", "parts":[], "figure":None} for n in range(1,total+1)]


class FinalPrintTests(unittest.TestCase):
    def test_spectra_and_work_function_count_as_atomic_physics(self):
        q=questions(1,1)[0]
        q["stem"]="来自三条谱线的光子分别照射逸出功不同的金属，判断产生光电子的条件。"
        r=exam_qa.inspect(ROOT,"physics",{"questions":[q]},["A"])
        self.assertEqual(r["coverage"]["原子物理"],[1])

    def test_every_physics_and_chemistry_nonchoice_position(self):
        for subject, choice, length in (("physics",10,15),("chemistry",14,18)):
            rows=questions(choice,length)
            for row in rows:
                row["figure"]={"path":"bound.png"}
            for n in range(choice+1,length+1):
                rows[n-1]["figure"]=None
                seen,issues=exam_qa.required_figure_issues(subject,rows)
                self.assertEqual({x for x,_,_ in issues},{0,n})
                self.assertNotIn(n,seen)
                rows[n-1]["figure"]={"path":"bound.png"}
            self.assertFalse(exam_qa.required_figure_issues(subject,rows)[1])

    def test_biology_counts_only_three_different_nonchoice_slots(self):
        rows=questions(16,21)
        for row in rows[:18]: row["figure"]={"path":"figure.png"}
        self.assertTrue(exam_qa.required_figure_issues("biology",rows)[1])
        rows[20]["figure"]={"path":"another.png"}
        self.assertEqual(exam_qa.required_figure_issues("biology",rows),([17,18,21],[]))

    def test_math_spatial_and_graph_dependent_tasks(self):
        rows=questions(1,3)
        rows[0]["stem"]="如图，求直线与椭圆的交点。"
        rows[1]["module"]="立体几何"
        rows[2]["stem"]="计算两个复数的和。"
        self.assertEqual([n for n,_,_ in exam_qa.required_figure_issues("math",rows)[1]],[1,2])

    def test_chinese_labels_read_back_from_bound_raster(self):
        with TemporaryDirectory() as d:
            folder=Path(d)
            path=folder/"plot.png"
            fig=Figure()
            FigureCanvasAgg(fig)
            fig.text(.5,.5,"Flux/mWb")
            with self.assertRaisesRegex(ValueError,"Flux"):
                exam_qa.save_figure(fig,path,subject="physics")
            exam_qa.save_figure(fig,path,subject="english")
            rows=questions(1,1)
            rows[0]["figure"]={"path":path.name,"sha256":digest(path)}
            record=exam_qa.inspect(ROOT,"physics",{"questions":rows},["A"],figure_folder=folder)
            self.assertIn("figure_language",[i["rule"] for i in record["issues"]])
            path.write_bytes(b"wrong")
            with self.assertRaisesRegex(ValueError,"哈希"):
                exam_qa.printed_figure_labels(rows[0]["figure"],folder)

    def test_standard_units_and_chinese_instrument_names(self):
        self.assertEqual(exam_qa.label_hits(["压差/kPa","磁通量/mWb","pH","光敏电阻","NaCl","U/V"],"physics"),[])
        self.assertEqual(set(exam_qa.label_hits(["air/liquid","Flux","LDR"],"physics")),{"air","liquid","Flux","LDR"})
        self.assertFalse(exam_qa.label_hits(["air"],"english"))

    def test_embedded_vs_mixed_and_long_response(self):
        q={"kind":"constructed_response","points":12,"stem":"填写数据","parts":[{"text":"①____ s"}]}
        self.assertEqual(answer_height(q),0)
        q["parts"].append({"text":"说明误差方向的依据。"})
        self.assertGreater(answer_height(q),0)

    def test_spelling_and_recitation_boundaries(self):
        self.assertNotEqual(normalize_gap("apart"),normalize_gap("a part"))
        self.assertNotEqual(normalize_gap("their"),normalize_gap("there"))
        self.assertEqual(normalize_gap(["东风","故里"]),normalize_gap("东风；故里"))
