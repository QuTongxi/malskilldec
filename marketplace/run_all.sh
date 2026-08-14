#!/usr/bin/env bash
# The whole market scan, unattended: frame -> sample -> static -> court.
#
#   nohup bash marketplace/run_all.sh > marketplace/.cache/run_all.log 2>&1 &
#
# Every stage is resumable, so re-running this after a kill picks up where it
# stopped: the frame and the tarball sample are cached on disk, `static.json` is
# reused if present, and the court skips any skill whose report already exists.
set -u
cd "$(dirname "$0")/.."
set -a; . ./.env; set +a

say() { echo; echo "=== $(date '+%H:%M:%S')  $*"; echo; }

say "waiting for the frame"
while [ ! -f marketplace/frame.json ] || pgrep -f "bin/python3 -u marketplace/build_frame" >/dev/null; do
    sleep 20
done
say "frame ready"
tail -12 marketplace/.cache/frame.log

say "downloading the sample"
uv run python -u marketplace/download_sample.py \
    --frame marketplace/frame.json --out marketplace/real_dataset_8k \
    --target 8000 --workers 16
test -d marketplace/real_dataset_8k || { echo "no dataset; stopping"; exit 1; }
uv run python -u marketplace/describe.py --manifest marketplace/manifest.json

say "static analysis over the whole sample"
uv run python -u marketplace/scan.py --dataset marketplace/real_dataset_8k \
    --out marketplace/scan --min-score 60 --static-only

say "the court, hardest first, within budget"
uv run python -u marketplace/scan.py --dataset marketplace/real_dataset_8k \
    --out marketplace/scan --min-score 60 --budget 600 --max-parallel 4

say "done"
