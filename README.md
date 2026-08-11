# Open H3 Context IR

Open H3 Context IR is a decision-oriented workflow for turning a user request and multimodal references into an English Context IR for MiniMax H3-Base-Ref2VA.

The project focuses on reference selection, conflict resolution, timeline design, artifact prevention, and conservative completion. Output formatting is handled as a final validation step rather than the main optimization target.

## Repository map

- `SKILL.md`: P0-P6 execution workflow.
- `references/case_law.md`: verified and hypothetical decision rules.
- `references/anti_artifact_phrasebook.md`: artifact-prevention triggers and language.
- `references/ref_guide_en.md`: Ref2VA Context IR format reference.
- `references/base_guide_en.md`: base video prompting reference.
- `alignment/ALIGN.md`: blind comparison and regression protocol.
- `tools/TOOLS.md`: tool contracts and implementation status.

## Setup

Python 3.12 is recommended. The media tools also require `ffmpeg` and `ffprobe` on `PATH`.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Cloud model tools (T3/T4/T8) use DashScope APIs and do not require local GPU model weights.

```bash
export DASHSCOPE_API_KEY="your_api_key"
export DASHSCOPE_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"   # VLM OpenAI compatible API (Beijing)
export DASHSCOPE_HTTP_BASE_URL="https://dashscope.aliyuncs.com/api/v1"           # ASR async HTTP API (Beijing)
```

If you use a workspace-specific endpoint or another region, override the corresponding `DASHSCOPE_*_BASE_URL` value.

## Usage

Inspect an asset:

```bash
python tools/asset_probe.py input.mp4
```

Lint a completed Context IR:

```bash
python tools/ir_linter.py context-ir.txt --duration 10
```

Run the full workflow in `SKILL.md`. Tool inputs, outputs, confidence gates, and fallback behavior are defined in `tools/TOOLS.md`.

Examples:

```bash
# T3 visual attributes (default model: qwen3-vl-plus)
python tools/visual_attributes.py input.jpg

# T8 cross-asset binder with explicit VLM model override
python tools/cross_asset_binder.py entities.json --model qwen3-vl-plus

# T4 ASR requires a publicly reachable audio URL (qwen3-asr-flash-filetrans)
python tools/speech_verbatim.py "https://example-bucket.oss-cn-beijing.aliyuncs.com/input.wav"
```

## Evidence status

Every repository rule must be marked `[VERIFIED: case-id]` or `[HYPOTHESIS]`. The case law takes precedence over workflow summaries when they conflict. Official output collection is subject to the current restrictions in `alignment/corpus/LICENSE_NOTE.md`; no collected official corpus or experiment output is included in this repository.
