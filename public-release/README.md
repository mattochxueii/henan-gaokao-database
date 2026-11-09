# 全国高考数学研究与 AI 命题

这是准备供维护者审查的开源候选版。初始数据库随包提供 5 道项目原创数学题、答案、解析及审阅证据。历史目录提供卷名、地区和来源。历史题目全文可在持有合法副本后导入本地库。命题、验证、检索和索引重建均可在没有恢复密钥时运行。

## 安装与查询

需要 Python 3.11 或以上版本。克隆候选代码后，在仓库根目录使用以下命令。Windows 可直接使用 `.venv\Scripts\python.exe` 代替激活虚拟环境。

```sh
python -m venv .venv
# Linux / macOS
. .venv/bin/activate
python -m pip install -r requirements.txt
python scripts/local_data.py init
python scripts/national_cli.py sqlite-query --year 2026 --series project-original --number 1
python scripts/local_data.py sources --year 2024
python -m unittest discover -s tests -v
```

`init` 校验 JSONL 并重建 SQLite 检索索引。SQLite 是可删除重建的派生数据。索引和导入包保存在 Git 忽略的 `.local-data/`。原创样题的 2026 表示样例年份。现成样卷与解析位于 [examples/pilot](examples/pilot)。

## 命题 Skill

```sh
python scripts/install_math_skill.py
python .agents/skills/henan-math/scripts/run.py research --series project-original --topic 数列
python .agents/skills/henan-math/scripts/run.py generate --engine template --mode mixed --output experiments/template-demo
```

支持项目内 `.agents/skills` 的宿主可直接加载。也可以用 `--destination` 安装到宿主的技能目录，并通过 `--database` 或 `HENAN_MATH_DB` 指定另一个数据库。相对链接要求 Windows 上数据库和安装目录位于同一盘符。

宿主 AI 可以按 [写作与验证协议](skills/henan-math/references/writing-protocol.md) 创作新的 v2 候选，再运行 `generate --engine ai --candidates <候选.json> --output <新目录>`。这会执行独立求解和中文排版，产生仅供盲审的学生卷。待 PDF 盲审与独立数学对照通过，按协议运行 `publish` 输出试卷及解析。模板模式提供参数化练习。可选的外部模型需要显式配置自己的 API 凭据，公开版不会把导入的本地题面放入该接口的提示词。宿主 AI 访问本地资料时仍应遵守资料许可和用户设置。

PDF 盲审需要 Poppler 的 `pdftoppm`。如系统未找到合适的中文字体，设置 `HENAN_MATH_FONT` 为你有权使用的中文字体文件路径。详见 [写作协议](skills/henan-math/references/writing-protocol.md)。

## 数据与贡献

[数据结构、历史来源与合法导入](docs/DATA.md)说明了六学科的资料接口、校验范围、可选个人备份及迁移方法。当前命题器面向数学。代码与项目自有内容的候选授权见 [LICENSE](LICENSE)。历史试题及上游资料的权利另行适用。提交改动前请读 [贡献指南](CONTRIBUTING.md)。
