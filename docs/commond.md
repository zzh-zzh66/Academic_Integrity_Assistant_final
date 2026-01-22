现在对应的命令是什么。
用户问现在对应的命令是什么。根据之前的对话，用户要导入的仓库是：
- 仓库地址：https://github.com/zzh-zzh66/coze-agent-private-data.git
- 源目录：知识库资料001
- 目标目录：coze_knowledge_origin/test
- 分支：main

所以命令应该是：
```bash
python scripts/github_to_storage.py \
    --repo https://github.com/zzh-zzh66/coze-agent-private-data.git \
    --source-path 知识库资料001 \
    --target-prefix coze_knowledge_origin/test
```

我还应该提醒用户注意那些包含半角括号的文件可能会失败。
根据你之前的需求，命令如下：

```bash
python scripts/github_to_storage.py \
    --repo https://github.com/zzh-zzh66/coze-agent-private-data.git \
    --source-path 知识库资料001 \
    --target-prefix coze_knowledge_origin/test
```

**如果需要跳过已存在的文件（增量更新）：**
```bash
python scripts/github_to_storage.py \
    --repo https://github.com/zzh-zzh66/coze-agent-private-data.git \
    --source-path 知识库资料001 \
    --target-prefix coze_knowledge_origin/test \
    --skip-existing
```

**注意事项：**
⚠️ 那些包含半角括号 `()` 的文件仍然会失败，建议先重命名这些文件：
- `6.《科研失信行为调查处理规则》（国科发监〔2022〕221号） (1).pdf`
- `5.《学位论文作假行为处理办法》（教育部令第34号） (1).pdf`
- `1.《关于进一步加强科研诚信建设的若干意见》(厅字〔2018〕23号）.pdf`
- `7.《哲学社会科学科研诚信建设实施办法》（社科办字〔2019〕10号） (1).pdf`

将文件名中的 `(` 改为 `（`，`)` 改为 `）` 后再运行脚本。



导入记录
记录文件：scripts/knowledge_import_record.json
记录格式：按数据集分组存储已导入文件路径
用途：实现增量更新，避免重复导入
命令如下：
python scripts/storage_to_knowledge.py \
    --prefix coze_knowledge_origin/test


python scripts/storage_to_knowledge.py \
    --prefix coze_knowledge_origin/test \
    --list-only

python scripts/storage_to_knowledge.py \
    --prefix coze_knowledge_origin/test \
    --force-import