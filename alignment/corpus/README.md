# Corpus

每个目录是一条单变量官方判例：

```text
{case_id}/
├── input/
│   ├── request_manifest.json
│   └── assets/
├── expected_verdict.md
├── collection_meta.json
├── official_response.json
├── official_ir.txt
├── our_draft.md
├── our_ir.txt
└── verdict_diff.md
```

执行顺序不可交换：

1. 写 `expected_verdict.md`。
2. T9 采集并封存 `official_ir.txt`。
3. 执行者不看 official，完成 `our_draft.md` 的 P0-P4。
4. 生成 `our_ir.txt` 并跑 T10。
5. 才打开 official，完成六维 `verdict_diff.md`。
6. 归因 (a) 修库后重新盲跑；归因 (c) 同探针重采。

被提前看过 official 的 case 在 `collection_meta.json` 中写 `blind_status: training_only`，永久退出评测集。
