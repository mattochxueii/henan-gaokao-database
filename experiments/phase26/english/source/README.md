# 英语复现入口

在项目根目录执行以下命令，复算八份源卷及英语 DNA 的文件校验值、三轮盲审评分、67 题独立解答、逐题编辑审稿、分项写作评分和最终发布绑定。

```powershell
python -X utf8 experiments/phase26/english/source/verify.py
```

命题上下文保存在此目录，来自 `authoring-context english --limit 250`。同目录的 `author.py` 与三个语料模块构成初稿，`revise.py` 重建第二轮修改，上级目录的 `final_revision.py` 根据第二轮实际意见重建第三轮。各版候选和作者参考答案亦按原版保留。原始 PDF 的校验值对应当次实际印刷文件；重新排印需绑定新文件的校验值。

如需用定稿候选在另一个空目录生成练习卷，可执行：

```powershell
python scripts/gaokao_platform.py simulate english 2027 experiments/phase26/english/candidate-final.json path/to/new-english-paper --context experiments/phase26/english/source/authoring-context.json --layout-mode practice
```

原卷的三席独立报告含全部逐题盲答，分别保存在各轮的 `board/roundN.json`。命题席与盲答核对可由 `signoff.py <定稿目录> 3 <新输出目录>` 重建；`finish.py` 将已经逐页核对的教师解析和听力 PDF 记录与学生卷的原始印刷意见绑定。`final/print-evidence` 保存教师侧的两份原始签收。发布记录保存在 `final/publication.json`。
