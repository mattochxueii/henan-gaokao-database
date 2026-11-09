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

全国扩容库另用national/config.json定位.private/national-reference，national/backup.json记录45个认证加密分片及149文件库存。使用另一个分离密钥：

```powershell
python scripts/national_cli.py restore --key <全国库密钥路径>
python scripts/national_cli.py validate
python scripts/national_cli.py build-index
python scripts/national_cli.py sqlite-query --year 2020 --series cn-new-gaokao-1 --number 18
```

旧库和全国库两个密钥不能互换。SQL索引由结构化原始数据重建，无需备份临时绝对路径。更新完整题面后须重建清单并使用新的备份版本，不能覆盖旧分片。原站许可只覆盖其自有整理贡献；不把它误解为底层全部试题的再分发许可。
