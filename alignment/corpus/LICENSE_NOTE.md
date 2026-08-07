# LICENSE NOTE — 官方输出采集与蒸馏闸门

检查日期：2026-08-04。

检查来源：

- MiniMax Open Platform Terms of Service，生效日 2026-03-30：`https://platform.minimax.io/protocol/terms-of-service`
- MiniMax API Privacy Policy，生效日 2026-03-30：`https://platform.minimax.io/protocol/privacy-policy`
- MiniMax H3 Community License Agreement：随 MiniMax H3 权重分发

## 当期结论

1. Open Platform 条款称，在适用法律允许范围内，客户保留输入与生成内容的所有权。
2. 同一条款允许 MiniMax 使用输入与生成内容来提供、维护、开发和改进服务。
3. 条款同时禁止在未获明确许可时复制/改编服务组成部分，并禁止 reverse engineering、反汇编、反编译或试图发现产品与服务的源代码、算法或目标代码。
4. 条款没有明确授予“用 API 输出训练或蒸馏替代模型”的许可。生成内容归属不能推导出模型蒸馏许可。
5. H3 开放权重许可证约束本地 H3-Base 的使用；它不替代 Open Platform 对收费 H3-Context-IR API 的服务条款。

## 执行裁决

- 只用自有或明确可商用素材；每个素材在 `request_manifest.json` 记录权利来源。
- T9 调用前必须人工阅读本文件并传 `--ack-license-note`。该参数只证明已知悉风险，不代表 MiniMax 授权。
- 官方输出当前只可进入内部行为评估与人工判例记录。禁止公开发布成套官方 IR corpus。
- **禁止把官方 API 输出用于 SFT、蒸馏或其他训练，直到取得 MiniMax 对该用途的书面许可。** 获得许可后，在本文件追加授权日期、授权主体、适用账号、用途范围与凭据存放位置；不得删除本结论。
- 系统性探针是否落入条款的 reverse-engineering 禁止范围存在法律不确定性。扩大采集规模前由账号主体取得 MiniMax 书面确认；未确认时只保留人工、小规模、非自动批量评估。
- 官方条款或模型版本更新后，本结论失效，所有旧判例降级为待重验。

这不是法律意见；它是仓库的最保守执行边界。
