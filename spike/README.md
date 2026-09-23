# Mappet Phase 0 spike

Throwaway Python pipeline to de-risk recognition quality before building the app.

```
graph (OSMnx) → candidate loops → silhouette PNGs → local CLIP → HTML eval grid
```

## Setup

```bash
cd spike
uv sync --extra clip   # includes torch + open-clip (CPU OK)
# or without CLIP:
uv sync --extra dev
```

## Commands

```bash
# T0.1 — build + cache walk graph for Zagreb centre
uv run mappet-spike build-graph --lat 45.8150 --lng 15.9819 --distance-km 5

# T0.2 — generate candidate loops
uv run mappet-spike loops --lat 45.8150 --lng 15.9819 --distance-km 5 -n 200

# T0.4 — full eval HTML grid (≥3 origins)
uv run mappet-spike eval \
  --origin 45.8150,15.9819,Zagreb \
  --origin 52.5200,13.4050,Berlin \
  --origin 51.5074,-0.1278,London \
  --distance-km 5 -n 150 --out output/eval
```

Open `output/eval/index.html` in a browser. Decision notes go in `FINDINGS.md`.

## Tests

```bash
uv run pytest
```
