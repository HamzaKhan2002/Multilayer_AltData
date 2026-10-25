"""Figure style shared with the deck: dark navy background, blue / violet / cyan accents, source line on every figure."""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from .paths import FIGURES  # noqa: E402

BG, PANEL, FG, MUTED = "#060c1a", "#0b1426", "#e2e8f0", "#94a3b8"
BLUE, VIOLET, CYAN, GREEN, AMBER, RED = "#60a5fa", "#a78bfa", "#22d3ee", "#4ade80", "#fbbf24", "#f87171"


def theme() -> None:
    plt.rcParams.update({
        "figure.facecolor": BG, "axes.facecolor": PANEL, "savefig.facecolor": BG,
        "axes.edgecolor": "#334155", "axes.labelcolor": FG, "axes.titlecolor": FG,
        "xtick.color": MUTED, "ytick.color": MUTED, "text.color": FG,
        "grid.color": "#1e293b", "grid.linewidth": 0.8, "axes.grid": True,
        "axes.spines.top": False, "axes.spines.right": False,
        "font.family": "DejaVu Sans", "font.size": 14, "axes.titlesize": 15, "axes.labelsize": 14,
        "legend.facecolor": PANEL, "legend.edgecolor": "#334155", "legend.labelcolor": FG,
    })


def finish(fig, name: str, source: str) -> None:
    """Add the source line in a strip under the figure (wrapped to the figure width, so it never overlaps the plot or is cut),
    then save PNG (300 dpi) and SVG in figures/. The strip height (share of the image) is written in the PNG metadata ("strip"),
    so that the deck can crop it exactly; the deck captions carry the sources."""
    import textwrap

    w, h = fig.get_size_inches()
    text = textwrap.fill(source, width=max(30, int(w * 12.5)))
    pt = 9.5
    s = (text.count("\n") + 1) * pt * 1.3 / 72 + 0.14  # strip height in inches
    fig.set_size_inches(w, h + s)
    k = h / (h + s)
    for ax in fig.axes:
        p = ax.get_position()
        ax.set_position([p.x0, s / (h + s) + p.y0 * k, p.width, p.height * k])
    for t in fig.texts:
        x, y = t.get_position()
        t.set_position((x, s / (h + s) + y * k))
    fig.text(0.012, 0.07 / (h + s), text, fontsize=pt, color=MUTED, ha="left", va="bottom", linespacing=1.3)
    fig.savefig(FIGURES / f"{name}.png", dpi=300, metadata={"strip": f"{s / (h + s):.5f}"})
    fig.savefig(FIGURES / f"{name}.svg")
    plt.close(fig)


def scale_bar(ax, h: int, w: int, px_per_km: float, km: float = 1.0, label: str = "1 km") -> None:
    """Scale bar at the bottom-left of an image of h x w pixels, with a dark halo so it reads on clouds and white tanks."""
    import matplotlib.patheffects as pe

    halo = [pe.withStroke(linewidth=4.2, foreground="black")]
    x0, y = 0.045 * w, 0.93 * h
    ax.plot([x0, x0 + px_per_km * km], [y, y], color="white", lw=3.2, solid_capstyle="butt", path_effects=halo)
    ax.text(x0 + px_per_km * km / 2, y - 0.02 * h, label, color="white", ha="center", va="bottom", fontsize=14,
            fontweight="bold", path_effects=halo)
