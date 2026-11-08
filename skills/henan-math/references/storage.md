# 存储和恢复

仓库的 database.json 使用相对路径。结构化分析与来源索引进入版本管理，候选原文和页图在 .private/math-reference。加密备份以private-data/parts中的63个分片保存，backup-parts.json记录顺序与哈希。恢复自动合并并验证完整密文，缓存位于.private/cipher-cache。

在新仓库根目录安装 requirements.txt，运行以下命令。密钥由所有者另外保管。

```powershell
python scripts/private_data.py restore --key <密钥路径>
python scripts/cli.py validate
python scripts/math_skill.py research --topic 数列
```

恢复检查认证加密、路径穿越、重复成员、解压大小和每文件SHA-256。目标已有目录时会停止，保护现有资料。新采集版本另建目录，更新清单后用新的密文路径和密钥进行备份。

不得将解密数据和恢复密钥提交Git。来源网址和原页定位仍需保留，候选版不会因为进入私有库而成为官方原卷。加密备份仅供本私有项目的访问连续性使用。
