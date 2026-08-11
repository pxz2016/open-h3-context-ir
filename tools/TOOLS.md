# TOOLS — Stub 契约总纲

每个工具是一个 stub，由普通 agent 探索补齐。**契约裁决先于实现**：每个 stub 写明
它服务于 SKILL.md 的哪一步裁决、输出必须让哪个判断成为可能。实现随便换，契约不许动。

通用规定：

- 输出一律 JSON，字段名以本文件为准；不确定的观测必须带 `confidence` 字段而不是猜成确定值
- 每个工具带 `fallback`：未实现/失败时 P0 如何降级，保证 skill 无工具也能跛行
- `done` 判据全部是**行为判据**（在指定测例上产出什么），不是代码判据
- 模型工具通过云 API 调用，不要求本地显存常驻

---

## T1 `asset_probe` — 素材物理事实

- **服务裁决**：P3 内容 vs 时长仲裁的物理边界；`<Video N>`/`<Audio N>` 合法性检查
  （2–15s、总时长、数量上限）
- **契约**：`in: 文件路径` → `out: {type, duration_s, fps, resolution, has_audio_track,
  audio_channels, sample_rate}`
- **实现指引**：ffprobe 一层皮
- **done**：任意 mp4/wav/png 给出无误的物理参数
- **fallback**：无。这是唯一不许缺席的工具（一行 ffprobe 而已）

## T2 `shot_ledger` — 切镜台账

- **服务裁决**：P2 中 `<Video N>` 时间结构束的引用裁决；editing/continuation 任务里
  P4 时间戳的**事实来源**（VLM 低帧率采样估不准毫秒级 cut 点，此工具存在的全部理由）
- **契约**：`in: 视频路径` → `out: [{shot_idx, start_ms, end_ms, keyframes: [抽帧路径×2-3],
  camera_motion_guess: {type, amplitude, speed, confidence}}]`
- **实现指引**：PySceneDetect(content mode) 切镜 + ffmpeg 抽帧；camera_motion_guess
  可先 stub 为 null，后续用光流或 VLM 补
- **done**：对官方羊羔源视频（模型卡 assets 可下载）产出的镜头边界与官方 IR 的镜头
  结构一致
- **fallback**：均匀抽帧 @2fps 直接给 VLM，时间戳标注 `confidence: low` 且 P4 禁止
  在 low confidence 时间戳上做 editing 类的精确对齐

## T3 `visual_attributes` — 属性束取证

- **服务裁决**：P2 引用裁决的全部原材料。**这是与 caption 工具的本质区别**：
  输出按可独立引用的属性束分列，每束都可能被单独 cite/discard/transfer
- **契约**：`in: 图片路径 | (视频路径, shot_idx)` → `out: {entities: [{entity_id,
  category, identity_hints, appearance, clothing, props, action, pose_expression}],
  environment, lighting, style, layout_text: {texts_verbatim: [], layout}, camera}`
  —— 束的划分与 SKILL.md P2 的十六束严格对应
- **实现指引**：DashScope OpenAI 兼容视觉 API（默认 `qwen3-vl-plus`）+ 强制 JSON schema 的提取 prompt。
  屏内文字必须 verbatim 抄录进 `texts_verbatim`，不许概括
- **done**：对羊羔案源视频产出的属性束，能仅凭 JSON（不看原视频）重建出官方
  subject_definitions 里 `<Subject 1>` 的全部定义要素（wavy blonde hair / pink suit /
  unbuttoned white shirt / silver rings / black lamb）——一个要素都不能少，
  官方定义就是本工具的召回率标尺
- **fallback**：原图/帧直接进改写模型上下文，属性束在改写时临场提取（大上下文换取证质量）

## T4 `speech_verbatim` — 逐字稿

- **服务裁决**：词曲内容束的 verbatim 复用（P5 纪律：原语言、原词、`[unclear]` 不猜）；
  P3 时长仲裁的台词清单
- **契约**：`in: 音频路径` → `out: [{speaker_tag, start_ms, end_ms, lang,
  text_verbatim, unclear_spans: []}]`
- **实现指引**：DashScope 异步文件转写（默认 `qwen3-asr-flash-filetrans`，`enable_words=true`）；
  该模型要求公网可访问 `file_url`，本地文件需先上传。低置信 span 必须转写为 `[unclear]` 而不是最优猜测——**宁缺毋猜是契约的一部分**（guide 5.4 法条）
- **done**：中英混合、含听不清段落的测试音频上，无一处猜词；`[unclear]` 位置与人工
  标注一致
- **fallback**：无音频理解时，音频只能按 `music_profile.fallback` 处理且禁止任何
  台词复用类裁决（宁可让 IR 少一个能力，不许幻觉台词）

## T5 `voice_timbre` — 音色画像

- **服务裁决**：audio reference 类任务中 `(Sx)` 音色描述的证据（guide：性别/年龄感/
  音高/语速/口音/质地）
- **契约**：`in: (音频路径, speaker_tag)` → `out: {gender_impression, age_impression,
  pitch, pace, texture, accent, delivery, confidence}`
- **实现指引**：Qwen3-Omni-30B-A3B 或 Qwen2-Audio；输出用语对齐官方 IR 的音色词汇表
  （从 ALIGN 采集的官方产物中聚类，如 calm male delivery / clear youthful voice）
- **done**：对羊羔案参考音频，产出与官方 "calm male voice timbre" 同义的画像
- **fallback**：仅凭视频画面推断说话人属性，全字段 `confidence: low`，P5 中音色措辞
  降级为最保守描述

## T6 `music_profile` — 音乐侧写

- **服务裁决**：audio reuse/reference 的引用维度拆分（曲风束 vs 节拍束 vs 信号本身）；
  P4 cut 踩节拍的节拍网格
- **契约**：`in: 音频路径` → `out: {instrumentation: [], tempo_bpm, structure:
  [{section, start_ms}], beat_grid_ms: [], dynamics, texture}`
  —— **全字段禁止情绪形容词**（guide 4.7 法条：只写物理属性）
- **实现指引**：librosa（bpm/beat grid/onset）+ 音频 LLM 描述乐器与结构
- **done**：一段流行乐产出的 beat_grid 能让 P4 把 cut 排在拍点 ±50ms 内
- **fallback**：无 beat grid 时 P4 禁用"踩音乐节拍"作为 cut 理由，只许踩台词间隙与动作点

## T7 `speech_budget` — 台词时长核算

- **服务裁决**：P3 内容 vs 时长仲裁；P4 时间预算表
- **契约**：`in: [{lang, text}], style_hints` → `out: [{est_ms, floor_ms, ceil_ms}]`
  + `total_with_pauses_ms`（含 15–25% 呼吸/停顿系数）
- **实现指引**：分语言语速常数表。**常数来源是 case_law E-2 探针**（回归官方成片实测），
  在此之前用占位常数（en≈2.7词/s，zh≈4.5字/s）并全量标注 `[HYPOTHESIS]`
- **done**：对官方咖啡店案三句台词的估时，与官方 cut 点（3.0s/5.0s）排布兼容
- **fallback**：无。纯查表计算，必须实现（几十行）

## T8 `cross_asset_binder` — 跨素材同一性

- **服务裁决**：P3 多主体绑定仲裁（一个 Subject 多来源定义 vs attribute_transfer 的
  事实前提）；防止把两个长得像的人错并成一个 Subject
- **契约**：`in: [entity_id × asset]` → `out: [{entity_pair, same_identity:
  true|false|ambiguous, evidence}]`
- **实现指引**：DashScope 视觉模型成对比对；`ambiguous` 是合法输出，
  此时裁决权上交 P3 并要求在草稿记录裁决理由
- **done**：给同一人不同穿着的两图判 same，给两个相似陌生人判 ambiguous 而非武断
- **fallback**：改写模型上下文内自行比对，绑定裁决全部显式写理由

## T9 `official_oracle` — 官方神谕（对齐核心）

- **服务裁决**：不服务生成，服务 ALIGN.md 的全部采集与比对。**这是本 skill 最重要的工具。**
- **契约**：`in: {instruction, assets, duration?, ratio?}` →
  `out: {official_ir_text, usage_tokens, task_meta}`（透传官方
  `/video-generation-v2-h3-context-ir` API）+ 本地落盘 `alignment/corpus/{case_id}/`
  （输入素材、指令、官方 IR、时间戳全存档）
- **实现指引**：MiniMax 开放平台 API 一层皮 + 存档规范；采集前查平台服务条款对输出
  用于蒸馏的约束并把结论写进 `alignment/corpus/LICENSE_NOTE.md`
- **done**：跑通模型卡 full-2k-ref2va 脚本的同款请求，取回与模型卡展示一致结构的 IR
- **fallback**：无 API 预算时降级为 B 级判例采集：用官方 App 生成成片，人工反推裁决
  （只能验证裁决方向，验证不了措辞）

## T10 `ir_linter` — 格式门（仆人）

- **服务裁决**：P6 第三道门。**只保证登记无误，救不了裁决错误**——它的全部断言译自
  guide 法条，一条不许自创
- **契约**：`in: ir_text` → `out: [{rule_id, guide_ref, severity, span, message}]`
- **断言清单（约30条，全部标注 guide 出处）**：六段齐全且有序；标签在 subject_definitions
  先定义后使用；task-type 前缀 ∈ 六合法值的 `+` 组合且不重复；editing 类 summary 首句
  固定句式；retention 枚举 ∈ {fully_preserved, partially_preserved, attribute_transfer,
  weak_reference} / 音频 ∈ {fully_copy, partially_copy, reference, weak_reference}；
  retention 里无 `(Sx)`；`[Shot 1]` 无时间戳、后续 `At MM:SS.mmm` 严格递增且 < 总时长；
  `<d>` 带语言标注、句末标点合法、无波浪号/emoji/装饰标点；voiceover 固定短语 + 唇闭声明
  尾随；屏内文字在双引号内；soundscape 1–4 句且不含台词歌词；non_diegetic 的 mood 词按
  case_law F-1 报 guide 冲突 warning，且仍强制物理音乐参数；生成类 detailed_description
  350–500 词（编辑类豁免）；
  `(Sx)` 首现顺序与正文发声顺序一致……
- **done**：对三个官方 IR 全绿零误报；对 20 个人工注错样本逐一命中
- **fallback**：改写模型自查 checklist（可靠性下降，允许）

## T11 `h3_base_judge` — 端到端终审（可选）

- **服务裁决**：ALIGN.md §4 的最终裁判——同输入的官方 IR 与本 skill IR 各喂本地
  H3-Base-Ref2VA 768p，盲评成片
- **实现指引**：大显存单卡路径：33B 中约 13B AdaLN 分支可预计算缓存，推理有效载荷
  ≈20B bf16 ≈40GB；Qwen3-VL-32B 文本编码先行计算后卸载；或直接用社区量化
  （Comfy-Org / DeepBeepMeep GPU-poor 方案）。慢没关系，这是评测通道不是服务
- **done**：跑通模型卡 reproducible-768p-ref2va 脚本并复现官方样片
- **fallback**：跳过端到端，对齐只做到 IR 层（ALIGN §3）——可接受但降一档说服力

---

## 实现入口

契约仍以本文件上文为准；下面只登记当前实现，不新增裁决规则。

| T | 入口 | 执行位置 | 当前行为边界 |
| --- | --- | --- | --- |
| T1 | `python tools/asset_probe.py ASSET` | CPU | ffprobe 物理事实，高置信 |
| T2 | `python tools/shot_ledger.py VIDEO --output-dir DIR` | CPU | PySceneDetect 切镜 + 每镜三帧；运镜保持 unknown |
| T3 | `python tools/visual_attributes.py ASSET [--frame-ms N] [--model MODEL_ID]` | network | DashScope `qwen3-vl-plus`（可覆盖），强制属性束 JSON |
| T4 | `python tools/speech_verbatim.py AUDIO_URL [--model MODEL_ID]` | network | DashScope 异步 `qwen3-asr-flash-filetrans`；需公网 URL；人工 unclear 审核前不得复用台词 |
| T5 | `python tools/voice_timbre.py AUDIO` | CPU | 只给信号物理画像；身份、年龄、口音不猜 |
| T6 | `python tools/music_profile.py AUDIO` | CPU | tempo/beat/RMS/频谱；乐器与语义段落无证据时留空 |
| T7 | `python tools/speech_budget.py INPUT.json` | CPU | E-2 校准前全量标 `[HYPOTHESIS]` |
| T8 | `python tools/cross_asset_binder.py INPUT.json [--model MODEL_ID]` | network | DashScope 视觉模型成对证据；不足即 ambiguous |
| T9 | `python tools/official_oracle.py CASE MANIFEST --ack-license-note` | CPU/network | 先预测、权限闸门、原样归档；训练用途硬拒绝 |
| T10 | `python tools/ir_linter.py IR [--duration S]` | CPU | 30 个 guide/phrasebook 确定性检查，不判断裁决质量 |
| T11 | `python tools/h3_base_judge.py MANIFEST` | CPU + remote GPU | 同模型同 seed 串行生成、A/B 随机化、三盲评表 |

模型 ID 与远端配置通过各入口参数或 `--help` 所列环境变量提供。T3/T4/T8 通过 DashScope API 调用，不再依赖本地 GPU 模型路径。
