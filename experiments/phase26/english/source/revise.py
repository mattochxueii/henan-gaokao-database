"""Keep the first candidate intact and assemble only the second-round corrections."""
import sys
from pathlib import Path
from author import ROOT, OUT, save, read_json

src=read_json(OUT/"candidate.json")
notes=read_json(OUT/"author-solutions.json")
changes=[]

def log(n,before,after,reason):
    changes.append(dict(number=n,original=before,revised=after,reason=reason))

m=src["materials"]["L01"]
before=m["text"]
m["text"]=before.replace("每段对话读两遍。","每段对话仅读一遍。")
log(1,before,m["text"],"第一节短对话的播放次数；按教研席程序性勘误改为一遍，独立朗读稿由同版排印。")
q=src["questions"][16]
before=dict(q["options"])
q["stem"]="What first made June doubt that the discs were medals?"
q["options"]["B"]="A photograph showed one in use."
q["options"]["C"]="She found them in the club office."
notes["items"][16]["reasoning"]="首先起疑来自不同筹码的号码重复且无姓名。照片是后来证实用途的证据；俱乐部办公室是发现的地点，尚未改变她最初的奖牌猜想。"
log(17,before,q["options"],"保留正确答案 A。用真实但时间较晚的照片和更早的办公室发现地点取代无文本依据的重量与盒上名字，并在设问写明 first。")
m=src["materials"]["T"]
old="I left it [54] _____ on the results chart."
new="But when I drew up the results chart, I [54] _____ that table."
assert old in m["text"]
m["text"]=m["text"].replace(old,new)
q=src["questions"][53]
q["options"]={"A":"left out","B":"numbered","C":"moved","D":"circled"}
notes["items"][53]["reasoning"]="四个过去式均能接 that table。上次复盘不计分，所以新平面图要留桌，新成绩表却不列该桌，选 left out。numbered 借正式比赛桌编号，moved 借前文转移棋盘，circled 借在平面图上标位，三者均混淆两种记录。"
log(54,old,new,"改成四个动词均可成句的结构，明确复盘桌在平面图上留位、在成绩表上不予登记，保留答案字母 A。第41—55题共用此文，全部重新盲读。")
log(50,"四项逐项另起行，与完形材料相隔两页","完形四项同行，紧接材料排出","印刷席指出跨页回读负担；保留50题各词与正确键。")
log(66,"邮件称呼和落款之间不含可书写区域，两段续写段首相邻","采用 practice 版式；称呼和落款之间可书写，两段续写各有独立书写区域","落实印刷席的两项写作区意见，保留两道任务和两段首句。")

save(OUT/"candidate-round2.json",src)
save(OUT/"author-solutions-round2.json",notes)
save(OUT/"revision-round2.json",{"first_round_folder":"round1","same_question_ids":True,"changes":changes})
