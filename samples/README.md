# 展示样卷

此目录用于存放通过当前安检、独立盲审及外部复核的展示卷。旧版试卷供回归测试使用。

在仓库根目录运行：

~~~bash
python scripts/gaokao_platform.py simulate math 2027 candidate.json output/math --context context.json
~~~

从命题上下文到发布的步骤见[使用教程](../docs/TUTORIAL.md)和[统一 Skill](../skills/gaokao-platform/SKILL.md)。
