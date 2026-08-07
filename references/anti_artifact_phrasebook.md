# Anti-Artifact Phrasebook — 防伪影句式触发规则

官方 IR 里反复出现一类"看似冗余"的句子。它们不是文采，是**用措辞替生成模型堵住已知失败模式**
的护栏——这是 guide 没有明文、但官方样例处处在用的经验层。本文件把它们整理成
**触发条件 → 必写句式 → 堵的是什么伪影** 的规则，P5 扩写时逐条比对，命中即写。

规则格式同 case_law：`[VERIFIED: 出处]` 或 `[HYPOTHESIS]`。

---

## 已验证条目

### PH-1 说话收口 `[VERIFIED: 羊羔案/咖啡店案]`

- **触发**：任何 `<d>` 台词结束，且该角色之后不再立即说话
- **必写**：嘴部终态 + 发声动作停止，并与声音停止精确同步。官方措辞库：
  `Exactly as his voice stops, his lips meet in a relaxed smile, and his jaw ceases speaking motion.`
  / `She closes her lips and ...` / `He closes his mouth into an apologetic smile ...`
- **堵**：台词结束后嘴部继续开合（对口型模型最常见的溢出伪影）
- **注意**：收口动作要接一个后续动作（守住饼干/抚摸狗），孤立的"闭嘴"会生成僵硬定格

### PH-2 画外音免口型 `[VERIFIED: base guide 4.4 法条 + 用语强制]`

- **触发**：`says in an off-screen voiceover`（措辞本身是固定短语，不许同义替换）
- **必写**：`<d>` 块后立即 `while his/her lips remain completely closed`
- **堵**：画外音被错误配上在场角色的口型

### PH-3 无台词群像静音声明 `[VERIFIED: 官方 I2VA 拉面案]`

- **触发**：画面中有明显在交谈/张嘴的人物，但没有为其分配 `<d>` 与 `(Sx)`
- **必写**：明示无声，官方措辞：`mouths moving in continuous, silent cadences of conversation`
  / `his mouth moving animatedly in a silent exchange`
- **堵**：模型给背景人物生成含混人声（音画错位 + 抢主声道）

### PH-4 动作落定 `[VERIFIED: 羊羔案 + 官方 T2VA 星舰案]`

- **触发**：每个镜头的最后一个动作、以及全片最后一镜
- **必写**：动作写到 settle 的终态并 hold：
  `... as the camera holds on this tranquil, sunlit state through the end of the video.`
  / `settle into the exact ... arrangement`。禁止让描述停在动作进行时
- **堵**：结尾姿态漂移、动作无限延伸、最后一帧崩坏

### PH-5 情绪肌肉化 `[VERIFIED: 星舰案]`

- **触发**：任何想写情绪/心理的冲动
- **必写**：翻译为可渲染的肌肉与动作：`her jaw clenches` / `her shoulders tensing as she
  visibly braces herself` / `she slowly closes her eyes`。情绪词只允许作为声音描述的修饰
  （with light annoyance 修饰语气）
- **堵**：不可渲染的语义被模型随机具象化

### PH-6 引用生效点显式化 `[VERIFIED: 羊羔案]`

- **触发**：音色参考 / 动作参考在某镜头实际生效
- **必写**：在生效处点名机制：`his mouth movements naturally syncing to the new dialogue,
  with his voice timbre referencing the calm male delivery from <Audio 2>`
- **堵**：参考关系只在定义区声明、正文不落地，导致生成时参考强度不足

### PH-7 声音事件挂锚 `[VERIFIED: 咖啡店案 A-4]`

- **触发**：任何点状音效（笑声/碰撞/铃声）
- **必写**：与视觉锚的时序关系：`begins immediately after the line and continues through
  the final frame`
- **堵**：音效漂移到错误时刻

### PH-11 非揭示性运镜不强造终点 `[VERIFIED: 星舰案]`

- **触发**：运镜只承担连续逼近、蓄能或压力累积，过程中没有新主体/空间/状态需要 reveal
- **必写**：运动类型与有意义的速度即可；星舰案合法使用 `pushing in slowly`，没有虚构终点目标
- **堵**：为了满足形式上的“终点声明”凭空添加特写目标、揭示物或构图变化，污染原有事件
- **边界**：真正承担 reveal/reframe 的运镜终点是否必须显式钉死仍待单变量探针确认

### PH-12 突变事件同步收声 `[VERIFIED: 星舰案]`

- **触发**：画面事件明确造成声场或配乐的瞬时状态切换（跃迁完成、断电、爆发后真空式余波）
- **必写**：把 soundscape 与 non-diegetic music 的停止点同时挂到该事件；星舰案在 jump 后让冲击声
  `cuts abruptly` 回空房间底噪，并让配乐 `snapping immediately into silence right after the jump`
- **堵**：视觉已进入余波状态，上一阶段的轰鸣或配乐仍无边界延续，破坏因果落点
- **边界**：普通 fade in/out 是否都要显式起止仍是 `[HYPOTHESIS]`

---

## 待挖掘条目（agent 按此协议补齐）

**挖掘协议**：取 ALIGN 采集的每条官方 IR，标注"功能上冗余、语义上重复"的句子——
它们几乎必然是护栏。归纳其触发条件与措辞，凡在 ≥2 条独立官方产物中复现即可转 VERIFIED。

优先怀疑对象（各对应一个已知的生成伪影家族）：

- **PH-8 [HYPOTHESIS] 手部交互**：持物/递物/手指动作的保护性写法（手是重灾区，
  官方对"手拿什么、怎么拿"的描写密度值得专门统计）
- **PH-9 [HYPOTHESIS] 屏内文字锁定**：logo/招牌/字幕的 verbatim + 位置钉死写法，
  H3 主打文字渲染，官方必有固定句式（结合 case_law B-5 探针一起采）
- **PH-10 [HYPOTHESIS] 多人身份防串**：两个以上 Subject 同框时防止外观互相污染的
  重锚定频率（每镜头重锚一次？动作交接时重锚？）
