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

Model-backed tools require their model paths explicitly, either through command-line arguments or the environment variables documented by `--help`. Large-model dependencies are intentionally not installed by the base requirements file.

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

## Evidence status

Every repository rule must be marked `[VERIFIED: case-id]` or `[HYPOTHESIS]`. The case law takes precedence over workflow summaries when they conflict. Official output collection is subject to the current restrictions in `alignment/corpus/LICENSE_NOTE.md`; no collected official corpus or experiment output is included in this repository.
