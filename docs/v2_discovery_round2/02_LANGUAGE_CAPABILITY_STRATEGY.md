# GlyphCue V2 Round 2：语言能力与扩展策略

研究日期：2026-10-03。状态：设计输入与候选排序；仅文档核验，尚无 GlyphCue V2 模型、声线、Windows 后端或语言质量实测。Round 1 原稿保持历史记录；本轮按 greenfield V2、Windows 优先、本地 ASR、翻译/TTS 本地优先及显式 BYOK、单旁白预设声线边界研究。

## 1. 建议结论

EN/ZH/FR 是首轮评价锚点，六方向翻译仍须分别验证，但不能成为领域模型或选择器的永久三语上限。语言扩展必须按阶段声明：可导入/编辑、可本地识别、某个有向翻译对、某条目标声线、可精确对齐、可渲染导出。只有这些能力的实际交集才能称为某一条完整工作流可用。

建议在三语锚点达标后，第一批增量研究西班牙语、意大利语、巴西葡萄牙语；德语同期研究字幕链，配音单独设门槛。第二批研究日语和韩语；阿拉伯语、印地语、泰语则作为复杂书写系统与候选缺口的专项研究。此顺序依据本次候选的交集和新增工程工作量，没有市场需求数据支持，也不等于发行语言数承诺。具体次序可由真实用户需求调整。

## 2. 上游覆盖与产品验证必须分栏

下表中 W 指 multilingual Whisper（候选为 small / large-v3-turbo / large-v3）；Q 指 Qwen3-ASR-1.7B；A 指 Qwen3-ForcedAligner-0.6B。所有“列出”只指上游模型/接口表；全部语言在 GlyphCue V2 的产品验证状态均为 **未测**。ASR 语言码依据 [Whisper tokenizer](https://github.com/openai/whisper/blob/main/whisper/tokenizer.py) 与 [Qwen ASR 模型卡](https://huggingface.co/Qwen/Qwen3-ASR-1.7B)；A 的范围依据其[独立模型卡](https://huggingface.co/Qwen/Qwen3-ForcedAligner-0.6B)。

翻译列是建议的最小测试边，不是模型质量声明；候选 Qwen3-4B-Instruct-2507 的模型卡和公开评测不能证明任意语言对的字幕翻译质量。先测 `en↔X` 是缩小实验矩阵，不能自动开放 `zh↔X`、`fr↔X`，更不能把多跳经英语转换伪装为直接翻译。[确切模型卡](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507)

| 层级与语言 | 本地 ASR 上游列出 | 有向翻译首测建议 | 预设本地 TTS 具体候选 | A 上游列出 | 主要新增成本与边界 |
|---|---|---|---|---|---|
| 锚点 EN | W/Q | 与 ZH/FR 双向 | Kokoro `af_heart`；Qwen CustomVoice `Ryan` | 是 | 分开记录 en-US/en-GB 口音；数字缩写、姓名与短句 |
| 锚点 ZH | W/Q Chinese | 与 EN/FR 双向 | Kokoro `zf_xiaobei`；Qwen `Serena` | 是 | 普通话识别与简繁输出分别评价；中文“词”不能由空格定义 |
| 锚点 FR | W/Q | 与 EN/ZH 双向 | Kokoro `ff_siwis`；Qwen `Ryan` 跨语试验 | 是 | fr-FR/fr-CA 不互相推定；法语原生预设声线覆盖偏薄 |
| 扩展 1：ES | W/Q | en→es、es→en | Kokoro `ef_dora`；Qwen `Ryan` 跨语试验 | 是 | 西班牙/拉美变体分别标记；倒问号、数字与连读 |
| 扩展 1：IT | W/Q | en→it、it→en | Kokoro `if_sara` | 是 | 重音、撇号、缩写与时长增长 |
| 扩展 1：pt-BR | W/Q 的 Portuguese，未细分口音验收 | en→pt-BR、pt-BR→en | Kokoro `pf_dora` 明确巴西葡语 | 是（Portuguese） | pt-BR 不能承诺 pt-PT；同名语言的韵律和词汇区别 |
| 扩展 1 条件：DE | W/Q | en→de、de→en | Qwen `Ryan` 跨语试验；Kokoro v1.0 声音表未列德语 | 是 | 复合词、变音符、ß、目标字幕长度；本地配音声线是独立 Gate |
| 扩展 2：JA | W/Q | en→ja、ja→en | Kokoro `jf_alpha`；Qwen `Ono_Anna` | 是 | 汉字/假名混排、读音、无空格分词、禁则与句长 |
| 扩展 2：KO | W/Q | en→ko、ko→en | Qwen `Sohee`；Kokoro v1.0 未列 | 是 | 韩文字素、空格纠错、敬语；新增 TTS 路线成本 |
| 专项 3：AR | W/Q | en→ar、ar→en | 本轮两条 TTS shortlist 均未列 | 否 | RTL/Bidi、数字和拉丁词混排、字形连接、方言/标准阿语边界 |
| 专项 3：HI | W/Q | en→hi、hi→en | Kokoro `hf_alpha`；Qwen CustomVoice 未列 | 否 | 天城文字组合/连字、数字朗读、aligner 缺口 |
| 专项 3：TH | W/Q | en→th、th→en | 本轮两条 TTS shortlist 均未列 | 否 | 无空格词边界、上下附标、断行；TTS/aligner 候选缺口 |

TTS 声线及语言覆盖来自 [Kokoro VOICES](https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md) 与 [Qwen CustomVoice 模型卡](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice)。Qwen 表列十种语言，原生预设声线描述只覆盖中/英/日/韩；其余语言能调用不等于具有对应母语口音的声音。上表 `Ryan` 跨语行是可重复实验候选，不是推荐其口音或自然度已经达标。

表中“未列”仅限这些确切候选，不表示世界上不存在该语言模型；“A 否”不阻止采用 ASR 段时间或人工时间编辑，也不要求将不支持语言强送到该 aligner。Qwen ASR 与 aligner 覆盖不一致，不能把 ASR 的语言列表复制到时间戳能力上。

## 3. 法语、中文与语言标签

建议把 source spoken-language、source/target written-language、voice locale 和 UI locale 设为不同属性。采用可扩展的 BCP 47 字符串和验证规则，并允许未知值 `und`，不要使用固定 `EN | ZH | FR` 枚举。BCP 47 可表达语言、文字、地区；语言标签本身不证明模型覆盖。[W3C 语言标签指南](https://www.w3.org/International/articles/language-tags/)

- 法语：单独保存 `fr-FR`、`fr-CA` 验收材料和声线适配结果。`fr` 只表示模型 API 的较粗语言选择；不能因为机器或用户位于加拿大就自动承诺加拿大法语配音。`ff_siwis` 的 G2P 映射是 `fr-fr`，上游数据身份也不足以证明其满足任一用户期望口音，仍需听评。
- 中文：普通话的语音识别、`zh-Hans` / `zh-Hant` 书面输出、地域词汇和粤语分别建档；简繁转换不等于翻译或方言识别。内部可记录 `cmn`（普通话）与 `yue`（粤语），适配器再映射到候选实际支持的 `zh` / `Chinese` / `Cantonese` 等值，未映射应显式拒绝或要求选择，不能默默当普通话。
- 保留用户指定的语言信息，不把 CLDR likely-subtags 的默认推断当作识别结果。CLDR 可用于显示名、别名规范化和 locale 匹配；不能据 fallback 判定两个地区的语音相同。[Unicode LDML/CLDR](https://unicode.org/reports/tr35/)
- 混语材料保存主语言及局部人工修订的语言提示；自动检测只是带来源的建议。第一版无需承诺每词语言检测，仍应能保留外语姓名、术语和人工文本。

## 4. 能力 manifest 的最小设计约束

这是领域接口建议，不是本次要实现的 schema。能力由资源与验证证据驱动，不能从下拉框或一个 `supportedLanguages` 数组推导全流程。

| 记录 | 必要字段或含义 |
|---|---|
| Stage capability | `asr / translation / tts / alignment / rendering`；本地/用户显式 BYOK；实际 provider、model ID、immutable revision、转换来源 |
| Language / pair | 原始 BCP 47 标签、规范形式、书写脚本、可选地区；翻译必须保存 `source→target` 两端，不能仅存目标语言 |
| Adapter mapping | 如 `fr-FR → fr`（Whisper）、`French`（Qwen）、`f + ff_siwis`（Kokoro）；标记映射丢失的地区/口音信息；实际运行时能力探测复核映射 |
| Voice | 确切模型与 voice ID、原生语言描述、可尝试目标语言、已验证 locale、声音资产/来源许可、attribution 文本与来源链接 |
| Runtime profile | Windows 版本/架构、CPU/GPU、后端、运行时 revision、量化、RAM/VRAM、依赖包与推理配置；资源可用性另行检测 |
| Evidence status | `upstream-listed / product-verified / experimental / unavailable`；测试集版本、逐阶段结果、验证日期和适用硬件；安装就绪是独立状态 |
| Alignment / rendering | 对齐单位及 offset 约定、支持语言；字形覆盖、字体版本/许可、换行/方向/渲染器版本及导出测试 |

候选语言可以在产品中被表达；只有匹配到已批准能力的操作才可启动。“上游支持、尚未验证”与“已验证但模型未安装”必须是不同状态。正式名单还需质量、许可、性能及导出四类证据；不得把一次 GPU 成功外推 CPU。

若某语言不能本地 ASR，应提供导入人工/已有时间字幕并编辑导出的路径，明确其来源。它不会产生“该语言可识别”的承诺。若 TTS 缺少可用声线，可继续字幕输出；云 TTS/翻译仅在用户主动选择 BYOK 后进入对应能力判定。ASR 不因本地失败自动上传到云端。

## 5. 文本编辑、时间与渲染成本

新增语言并非增加一张标签表。下列设计约束应进入编辑与导出原型的验收，三语锚点本身已经能暴露其中数项。

| 层面 | 必须处理的语义 | 最小检查例子（合成文本） |
|---|---|---|
| 字符与光标 | code point、UTF-16 单元、字素簇不等价；删除/选取/拆段不得切开组合字符 | `é` 与 `e` + 组合重音的可视一致性；韩文组合、天城文字、emoji |
| 词/句切分 | 空格不能作为全部语言的“词”；缩写点号也不总是句末 | 中文无空格、日语混写、法语撇号、泰语词边界 |
| 换行 | 找到允许断行位置后还需按字体像素宽度、双语布局和字幕语义选断点 | 汉字标点不落在错误行首；法语标点空白；德语长词不被裁切 |
| 方向与整形 | 逻辑文本顺序、Bidi 显示顺序、字形整形分别处理，编辑器与成片需一致 | 阿拉伯文 + `2026` + 拉丁产品名 + 括号；双语各行方向 |
| 大小写/搜索 | 搜索规范化不能破坏原文；大小写不是一对一转换；locale-aware 规则可扩展 | 德语 ß 与 SS；法语重音匹配策略；未来土耳其语 I/i |
| 数字与读音 | 字幕显示文本与 TTS 读法可不同，但应可追溯；日期货币不能自动套系统 locale | `1,5`、`1.5`、缩写、编号、中文多音字与日文姓名 |
| 时间引用 | provider 的“word”可能是字符/子词；offset 必须带单位与原始文本版本 | 文本改为 NFC 或拆合 cue 后，旧词级对齐显式失效；不能继续沿用错误字符跨度 |

以上边界依据 [UAX #29 字素/词/句分段](https://www.unicode.org/reports/tr29/)、[UAX #14 换行](https://www.unicode.org/reports/tr14/)、[UAX #9 双向算法](https://www.unicode.org/reports/tr9/)。它们定义基础行为，字幕语义断句、每行长度与阅读速度仍是产品策略。ICU BreakIterator 提供这些基础分段及部分语言词典机制，同时明确默认规则不能替代全部语言分析；应通过选定 GUI/文本栈使用这些能力，不自行堆正则表达式。[ICU boundary analysis](https://unicode-org.github.io/icu/userguide/boundaryanalysis/)

建议原始 ASR 文本、人工修订和用于比较/检索的规范化文本分开；归一化不能改变已绑定字符 offset 的原文。显示长度以字素和实际排版宽度检查，阅读速度阈值按语言验证，不把统一英文字数当作三语标准。TTS 分段按语意和时长，字幕行按可读性，二者不强制一一相等。

字体采用明确可再分发的精确文件及版本，保存字体 fallback 和字形检查结果。Noto Latin/Greek/Cyrillic 仓的 [OFL 文本](https://github.com/notofonts/latin-greek-cyrillic/blob/main/OFL.txt)是可评估例子，但不能据此推定所有 Noto 包文件、系统字体或 CJK/阿拉伯字体都已审完。离线导出包必须带已批准字体，不能以开发机上“能显示”替代冷安装验收。

## 6. 按资产审许可，不能按家族一概批准

下表是候选的文档层许可核验。实际商用/捆绑放行仍要固定 revision、准确文件、转换链、依赖和通知；“未发现额外单声线许可证”不等于已取得某真实人物声音的所有权利。

| 具体资产 | 已核对层次 | 对 GlyphCue 的约束 |
|---|---|---|
| OpenAI multilingual Whisper | 官方说明代码与权重 MIT | 保留许可通知；第三方运行时与量化产物另记来源。[官方许可](https://github.com/openai/whisper#license) |
| Qwen3-ASR-1.7B / Qwen3-ForcedAligner-0.6B | 各模型卡 Apache-2.0，ASR 项目源码 Apache-2.0 | 仅用于这里列出的具体资产；不能替其他 Qwen 模型作结论。[源码](https://github.com/QwenLM/Qwen3-ASR)、[ASR 卡](https://huggingface.co/Qwen/Qwen3-ASR-1.7B)、[aligner 卡](https://huggingface.co/Qwen/Qwen3-ForcedAligner-0.6B) |
| Qwen3-4B-Instruct-2507 + llama.cpp | 该权重 Apache-2.0；llama.cpp MIT | 分别收集许可/通知和实际 GGUF 转换信息；不构成任意语言对质量批准。[权重 LICENSE](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507/blob/main/LICENSE)、[runtime LICENSE](https://github.com/ggml-org/llama.cpp/blob/master/LICENSE) |
| Qwen3-TTS-12Hz-1.7B-CustomVoice + Tokenizer-12Hz | 源码、该模型卡、该 tokenizer 卡均列 Apache-2.0；本轮未找到各内置 voice ID 单独权利保证 | 本轮只研究预设声线，不启用 Base 克隆或 VoiceDesign；归档确切声线描述与上游通知，不能从家族名承诺所有声音。[代码](https://github.com/QwenLM/Qwen3-TTS)、[CustomVoice](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice)、[tokenizer](https://huggingface.co/Qwen/Qwen3-TTS-Tokenizer-12Hz) |
| Kokoro-82M v1.0 与列出声音 | 代码/权重 Apache-2.0；模型卡另列 SIWIS CC BY 4.0、Koniwa CC BY 3.0 训练来源 | `ff_siwis` 和部分日语声音的来源/署名链必须保留；不要把数据来源的 CC BY 自动改写为模型全部输出的同一许可证，也不要忽略署名链。[代码许可](https://github.com/hexgrad/kokoro/blob/main/LICENSE)、[模型卡 attribution](https://huggingface.co/hexgrad/Kokoro-82M)、[SIWIS 原始记录](https://datashare.ed.ac.uk/handle/10283/2353) |
| Kokoro 的 G2P 依赖 | Misaki 仓列 Apache-2.0；若带 eSpeak NG，其代码 GPL-3.0-or-later | 按最终语言包盘点实际包含的 G2P/词典/语音数据及许可证；声学权重许可不能覆盖分发依赖。[Misaki](https://github.com/hexgrad/misaki)、[eSpeak NG COPYING](https://github.com/espeak-ng/espeak-ng/blob/master/COPYING) |

若未来选择 BYOK 服务，模型本地权重许可不适用于云服务合同。能力记录还应包含 provider/region/voice ID、条款日期、输入用途/留存、输出商业使用、缓存和费用限制；接入前按具体服务审查。本轮没有选定或调用外部 TTS/翻译服务。

## 7. 下一步最小验证与退出条件

第一步先完成 EN/ZH/FR 锚点：六个翻译方向各自听读校验；法语声线对 `fr-FR` 与 `fr-CA` 的结果分栏，普通话识别与简繁书面文本分栏。这些尚未实测的边界不能由新增语言覆盖数掩盖。

第二步每次只新增一种语言的一条完整路径。建议 ES 先行：获授权、带参考转录的短语音；先本地 ASR，再 en→es 与 es→en 两方向，最后固定一条声线和字体导出。具体采样数量和质量阈值由实验计划统一管理；本报告不额外伪造通过线。记录严重漏译/数字错误、人工修订时间、段边界误差、字幕溢出、实际配音时长、离线资源和许可缺项。

第三步先用合成文字（无需模型）验证 JA/KO/AR/HI/TH 的编辑、字素拆分、布局、选区和导出设计；这只证明文本/渲染可行，不能称为这些语言的 ASR/TTS 已支持。文档已足以确定现阶段能力边界，因此本轮没有制作原型、下载模型或运行推理。只有选定 UI/渲染栈后仍有无法通过资料回答的行为，才创建对应一次性原型。

产品 Gate：语言层级是研究优先级；发行名单待逐项证据。新增语言若识别/翻译不达标，保持导入字幕编辑路径；TTS 或对齐未达标，限制相应阶段。不得自动选云端、克隆声音或引入声源分离来填补缺口。

## 8. 证据版本边界

上述官方网页、源码和模型卡均于 2026-10-03 在线核验；大多链接指向上游 main/当前页面，可能变化。本轮未下载权重，未生成固定资源 manifest，也未进行商用发行批准。Design 后的技术选择必须冻结精确模型 revision、运行时/字体版本和许可快照，才可将“上游列出”提升为受控候选；完成对应硬件与语言验收后才可提升为产品已验证。
