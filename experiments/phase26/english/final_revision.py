"""Apply the three grammar-uniqueness findings to the second, independently scored edition."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
def load(name):return json.loads((ROOT/name).read_text(encoding="utf-8-sig"))
def save(name,data):(ROOT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

p=load("candidate-round2.json")
a=load("author-solutions-round2.json")
decision=load("round2/board/decision.json")
assert decision["round"]==2 and set(decision["rewrite"])=={58,62,64}
m=p["materials"][p["questions"][57]["material"]]
changes=[
 ("阅读下面短文，在空白处填入1个适当的单词或括号内单词的正确形式。","阅读下面短文，在空白处填入适当的单词或括号内单词的正确形式，每空限填一词。"),
 ("Among the blocks was [58] _____ unusually large question mark.","One block printed such [58] _____ unusually large question mark that it would scarcely fit on a postcard."),
 ("Even a short message takes time, and the guides wait [62] _____ (patient) while a visitor works.","One child set the type so carefully that her print matched the guide’s sample [62] _____ (exact), right down to a hairline gap."),
 ("The letters may be straight, but one may print a little [64] _____ (dark) than the rest.","Three impressions from the same block hang by the door: one is pale grey, one is almost black and one is jet black. Of the three, the last is the [64] _____ (dark).")]
for old,new in changes:
    assert m["text"].count(old)==1,old
    m["text"]=m["text"].replace(old,new)
for n,word,reason in [(58,"an","such + 不定冠词 + 形容词 + 单数可数名词。unusually 以元音音素开头。"),
                      (62,"exactly","印样连细缝也一丝不差；修饰 matched，exact 的副词形式是 exactly。"),
                      (64,"darkest","比较三种墨色，最后一张最深。the 与三者比较要求形容词最高级；按每空一词填 darkest。")]:
    p["questions"][n-1]["answer"]=word
    a["items"][n-1].update(answer=word,reasoning=reason)
save("candidate-final.json",p)
save("author-solutions-final.json",a)
save("revision-round3.json",{"previous_pdf":decision["pdf_sha256"],"reason":decision["deductions"],"changes":changes,
                            "affected_passage_questions":list(range(56,66))})
