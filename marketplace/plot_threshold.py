"""Precision, recall and F1 of the static stage as the claim-score cut moves.

    uv run python marketplace/plot_threshold.py -o marketplace/figs/threshold_sweep.pdf

The static stage does not return a verdict, it returns a score, so "how good is
static alone" is not a number but a curve.  Reading one row of it -- "a skill
with any claim is malicious" -- is the left edge of this plot, and it is the
worst operating point on it: on the 100+100 set that rule flags 178 of 200
skills, for a precision of 0.562.

Labels come from the dataset layout (`.../malicious/...` vs `.../benign/...`),
scores from `static.json`.  The scores are integers, so a cut-by-cut sweep draws
a staircase; the curves are therefore sampled on a sub-integer grid and passed
through a centred moving average whose width is stated in score points.  Every
plotted value is an average of exact measurements -- nothing is interpolated or
modelled.  The sweep stops just past the highest-scoring benign skill, because
beyond that point precision is pinned at 1.0 and only recall falls.

The score scale depends on how the report was produced: the default model runs
to a few hundred, `--simplify-score` to a few dozen.  The axis, its ticks and
the smoothing width therefore all follow the data rather than fixed constants.

No figure title -- the caption belongs to the paper, not the PDF.
"""

import argparse
import json
import math
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Okabe-Ito: the standard colour-blind-safe palette for print, and the usual
# paper blue / green / orange.  Validated all-pairs on a light surface -- worst
# CVD dE 11.0 (deutan), worst normal-vision dE 18.7, all three over 3:1 contrast.
# The textbook blue/green/orange sets do NOT pass: under protanopia matplotlib's
# tab10 green and orange land dE 0.7 apart, which is the same colour, and
# ColorBrewer Set1's pair sits at 5.3, under the floor of 6.
BLUE, GREEN, ORANGE = "#0072B2", "#009E73", "#D55E00"
INK, INK_2 = "#111111", "#555555"
GRID = "#d9d9d9"


def moving_average(values, half, passes=1):
    """Centred mean, window shrinking at the ends so both ends stay anchored.

    Chosen over a spline because it cannot overshoot into impossible territory
    (no precision of 1.03) and because the mean of a monotone sequence is still
    monotone -- recall is non-increasing in the cut by construction, and the
    smoothed recall stays non-increasing too.  A spline guarantees neither.

    A second pass turns the boxcar into a triangular kernel, which removes the
    corner a single pass leaves at every integer score.  Both properties above
    survive it: an average of averages is still a positive-weight average.
    """
    for _ in range(passes):
        out = []
        for i in range(len(values)):
            lo, hi = max(0, i - half), min(len(values), i + half + 1)
            out.append(sum(values[lo:hi]) / (hi - lo))
        values = out
    return values


def nice_bound(value):
    """Smallest round number strictly above `value`, in at most 8 round steps."""
    for unit in (1, 2, 5, 10, 20, 25, 50, 100, 200, 500, 1000):
        steps = math.floor(value / unit) + 1
        if steps <= 8:
            return unit * max(steps, 4)
    return int(value) + 1


UNITS = (1, 2, 4, 5, 10, 20, 25, 50, 100, 200, 500, 1000)


def tick_unit(bound):
    """Tick spacing that divides the axis evenly into 3 to 6 intervals."""
    for unit in UNITS:
        if bound % unit == 0 and 3 <= bound // unit <= 6:
            return unit
    # nothing round splits this axis into 3-6: take the divisor closest to 5,
    # so the last tick still lands exactly on the right edge
    divisors = [u for u in UNITS if bound % u == 0] or [1]
    return min(divisors, key=lambda u: abs(bound // u - 5))


def curves(static_path, hi=None, half=5.0, step=1.0, passes=1):
    report = json.load(open(static_path, encoding="utf-8"))
    malicious, benign = [], []
    for skill in report["skills"]:
        top = max((claim["score"] for claim in skill["claims"]), default=0)
        (malicious if "malicious" in skill["path"] else benign).append(top)

    # Past the best-scoring benign skill precision can only be 1.0, so that is
    # where the interesting part of the sweep ends.
    if hi is None:
        hi = nice_bound(max(benign, default=1))

    def score(cut):
        tp = sum(1 for v in malicious if v >= cut)
        fp = sum(1 for v in benign if v >= cut)
        p = tp / (tp + fp) if tp + fp else 1.0
        r = tp / len(malicious)
        return p, r, (2 * p * r / (p + r) if p + r else 0.0)

    # A cut is an integer, so the curve is a staircase and each tread has to be
    # placed somewhere.  Centre it: x is the cut nearest x, which puts the tread
    # for cut t on [t-0.5, t+0.5).  Taking the cut *above* x instead would park
    # every tread's right edge on its own label, and the smoothing there would
    # read half its window off the neighbouring, lower tread -- which drags the
    # F1 maximum visibly below the curve's own peak.  At step=1 the two agree.
    cuts = [i * step for i in range(int(round(hi / step)) + 1)]
    measured = [score(math.floor(c + 0.5)) for c in cuts]
    raw_p = [m[0] for m in measured]
    raw_r = [m[1] for m in measured]
    raw_f = [m[2] for m in measured]

    # Smooth the two measured quantities and recompute F1 from them, rather than
    # smoothing F1 on its own -- that keeps the three curves mutually consistent,
    # so the drawn F1 is still the harmonic mean of the drawn P and R.
    half_idx = int(round(half / step))
    smooth_p = moving_average(raw_p, half_idx, passes)
    smooth_r = moving_average(raw_r, half_idx, passes)
    smooth_f = [2 * p * r / (p + r) if p + r else 0.0 for p, r in zip(smooth_p, smooth_r)]

    # Scores are integers, so report the integer cut the winning tread stands for.
    peak = math.floor(cuts[max(range(1, len(cuts)), key=lambda i: raw_f[i])] + 0.5)
    drift = max(max(abs(a - b) for a, b in zip(smooth_p, raw_p)),
                max(abs(a - b) for a, b in zip(smooth_r, raw_r)))
    return {"cuts": cuts, "raw": (raw_p, raw_r, raw_f),
            "smooth": (smooth_p, smooth_r, smooth_f),
            "peak": peak, "at_peak": score(peak), "at_one": score(1),
            "drift": drift, "hi": hi, "n_mal": len(malicious), "n_ben": len(benign)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--static", default="eval_runs/run_100x100/static.json")
    parser.add_argument("-o", "--output", default="marketplace/figs/threshold_sweep.pdf")
    parser.add_argument("--smooth", type=float, default=5.0,
                        help="half-width of the centred moving average, in score points "
                             "(0 draws the raw staircase)")
    parser.add_argument("--hi", type=float, default=None,
                        help="right edge of the sweep (default: just past the "
                             "highest-scoring benign skill)")
    parser.add_argument("--step", type=float, default=1.0,
                        help="sampling step of the sweep grid, in score points; below 1 "
                             "it resolves the staircase the smoothing then rounds off")
    parser.add_argument("--passes", type=int, default=1,
                        help="moving-average passes; 2 gives a triangular kernel and "
                             "drops the corner left at every integer score")
    args = parser.parse_args()

    data = curves(args.static, hi=args.hi, half=args.smooth,
                  step=args.step, passes=args.passes)
    grid = data["cuts"]
    hi = data["hi"]
    raw_p, raw_r, raw_f = data["raw"]          # kept for the console summary
    precision, recall, f1 = data["smooth"]
    peak = data["peak"]
    peak_p, peak_r, peak_f1 = data["at_peak"]

    # Mark the vertices only when every one of them is a measured operating
    # point -- an unsmoothed sweep over the integer cuts.  Once the curve is
    # smoothed, or sampled between the integers, the vertices are no longer
    # measurements and dotting them would claim more than the data says.
    #
    # Three shapes, not three copies of one shape: shape is a second channel
    # that survives a greyscale print and any colour-vision deficiency, which
    # colour alone does not.  Size follows the >=8px rule and each marker
    # carries a ring in the surface colour, so where two series cross the dots
    # stay separable -- undersized dots just read as dirt on the line.
    marked = args.smooth == 0 and args.step == 1

    def vertex(shape):
        return dict(marker=shape, markersize=5.5, markeredgecolor="white",
                    markeredgewidth=1.0) if marked else {}

    plt.rcParams.update({
        "pdf.fonttype": 42, "ps.fonttype": 42,     # embed TrueType, keep text selectable
        "font.family": "sans-serif",
        "font.sans-serif": ["DejaVu Sans"],
        "font.size": 10, "axes.labelsize": 11,
        "xtick.labelsize": 9.5, "ytick.labelsize": 9.5, "legend.fontsize": 9.5,
    })

    figure, axes = plt.subplots(figsize=(6.4, 4.2))
    figure.patch.set_facecolor("white")
    axes.set_facecolor("white")

    # a closed rectangle, all four sides
    for spine in axes.spines.values():
        spine.set_visible(True)
        spine.set_color(INK_2)
        spine.set_linewidth(0.9)
    axes.grid(True, which="major", color=GRID, linewidth=0.6, zorder=0)
    axes.set_axisbelow(True)
    axes.tick_params(direction="out", colors=INK_2, length=3.5, width=0.9,
                     top=False, right=False)

    # guides to both axes at the F1 maximum, drawn under the curves
    axes.plot([peak, peak], [0, peak_f1], color=INK_2, linewidth=0.9,
              linestyle=(0, (4, 3)), zorder=2)
    axes.plot([0, peak], [peak_f1, peak_f1], color=INK_2, linewidth=0.9,
              linestyle=(0, (4, 3)), zorder=2)

    axes.plot(grid, precision, color=BLUE, linewidth=1.9, solid_capstyle="round",
              zorder=3, label="Precision", **vertex("o"))
    axes.plot(grid, recall, color=GREEN, linewidth=1.9, solid_capstyle="round",
              zorder=3, label="Recall", **vertex("s"))
    axes.plot(grid, f1, color=ORANGE, linewidth=1.9, solid_capstyle="round",
              zorder=3, label="F1", **vertex("^"))

    # Emphasise the optimum by enlarging its own vertex, so it reads as "this
    # point" rather than as a fourth kind of mark dropped onto the chart.
    axes.plot([peak], [peak_f1], marker="^" if marked else "o",
              markersize=9.0 if marked else 5.5, color=ORANGE,
              markeredgecolor="white", markeredgewidth=1.2, zorder=5)

    axes.set_xlim(0, hi)
    axes.set_ylim(0, 1.02)

    # the cut that maximises F1 gets its value onto both axes, beside the round numbers
    unit = tick_unit(int(hi))
    rounds = [unit * i for i in range(int(hi) // unit + 1)]
    axes.set_xticks(rounds + [peak])
    axes.set_yticks([0.0, 0.2, 0.4, 0.6, 0.8, 1.0] + [peak_f1])
    axes.set_xticklabels(["%d" % t for t in rounds] + ["%d" % peak])
    axes.set_yticklabels(["0.0", "0.2", "0.4", "0.6", "0.8", "1.0", "%.3f" % peak_f1])
    for label, value in zip(axes.get_xticklabels(), rounds + [peak]):
        if value == peak:
            label.set_color(ORANGE)
    for label, value in zip(axes.get_yticklabels(),
                            [0.0, 0.2, 0.4, 0.6, 0.8, 1.0, peak_f1]):
        if value == peak_f1:
            label.set_color(ORANGE)

    axes.set_xlabel("claim-score threshold", color=INK)

    legend = axes.legend(loc="lower left", frameon=True, framealpha=1.0,
                         edgecolor=GRID, facecolor="white", handlelength=2.0,
                         borderpad=0.5, labelspacing=0.4)
    legend.get_frame().set_linewidth(0.8)
    for text in legend.get_texts():
        text.set_color(INK)

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    figure.tight_layout()
    figure.savefig(args.output, format="pdf", bbox_inches="tight", facecolor="white")
    figure.savefig(args.output.replace(".pdf", ".png"), format="png",
                   bbox_inches="tight", facecolor="white", dpi=240)
    print("wrote %s (%d cuts over 0..%d, %d malicious + %d benign, "
          "smoothing half-width %g x %d pass)"
          % (args.output, len(grid), hi, data["n_mal"], data["n_ben"],
             args.smooth, args.passes))
    print("max |smoothed - raw| = %.3f" % data["drift"])
    print("F1 max %.3f at t = %d  (P %.3f, R %.3f)" % (peak_f1, peak, peak_p, peak_r))
    print("t = 1 'any claim'      :  P %.3f, R %.3f, F1 %.3f" % data["at_one"])


if __name__ == "__main__":
    main()
