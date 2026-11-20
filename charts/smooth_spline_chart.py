import numpy as np

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from scipy.interpolate import make_interp_spline

from config.theme_tokens import chart_colors, glow_enabled


class ModernSplineChart(FigureCanvas):
    def __init__(self, parent=None):
        self.fig = Figure(figsize=(8, 3.5))

        super().__init__(self.fig)

        self.setParent(parent)

        self.ax = self.fig.add_subplot(111)

        self._setup_theme()

    def _setup_theme(self):
        colors = chart_colors()

        self.fig.set_facecolor(colors["figure"])
        self.ax.set_facecolor(colors["axes"])
        self.ax.title.set_color(colors["text"])
        self.ax.xaxis.label.set_color(colors["text"])
        self.ax.yaxis.label.set_color(colors["text"])

        self.ax.tick_params(
            colors=colors["muted"],
            labelsize=10,
        )

        for spine in self.ax.spines.values():
            spine.set_color(colors["border"])

        self.ax.grid(
            True,
            linestyle="--",
            linewidth=0.6,
            color=colors["border"],
            alpha=0.8,
        )

    def plot_trend(self, x_data, y_data, label="OPS"):
        self.ax.clear()

        self._setup_theme()

        x = np.asarray(x_data, dtype=float)
        y = np.asarray(y_data, dtype=float)

        valid = np.isfinite(x) & np.isfinite(y)

        x = x[valid]
        y = y[valid]

        if not len(x):
            colors = chart_colors()

            self.ax.text(
                0.5,
                0.5,
                f"No {label} trend data",
                ha="center",
                va="center",
                transform=self.ax.transAxes,
                color=colors["text"],
            )

            self.fig.tight_layout()
            self.draw()
            return

        order = np.argsort(x)

        x = x[order]
        y = y[order]

        unique_x, inverse = np.unique(
            x,
            return_inverse=True,
        )

        if len(unique_x) != len(x):
            totals = np.bincount(
                inverse,
                weights=y,
            )

            counts = np.bincount(inverse)

            x = unique_x
            y = totals / counts

        if len(x) > 3:
            x_new = np.linspace(
                x.min(),
                x.max(),
                200,
            )

            spl = make_interp_spline(
                x,
                y,
                k=3,
            )

            y_smooth = spl(x_new)

        else:
            x_new = x
            y_smooth = y

        colors = chart_colors()

        # Glow 레이어
        if glow_enabled():
            self.ax.plot(
                x_new, y_smooth, color=colors["primary"], linewidth=7,
                alpha=0.18, solid_capstyle="round", label="_glow",
            )

        # 실제 라인
        self.ax.plot(
            x_new,
            y_smooth,
            color=colors["primary"],
            linewidth=2.5,
            label=label,
            solid_capstyle="round",
        )

        # 영역 채우기
        self.ax.fill_between(
            x_new,
            y_smooth,
            min(0.0, float(y.min())),
            color=colors["primary"],
            alpha=0.12,
        )

        # 데이터 포인트
        self.ax.scatter(
            x,
            y,
            color=colors["primary"],
            s=36,
            edgecolors=colors["text"],
            linewidth=1.5,
            zorder=5,
        )

        self.fig.tight_layout()

        self.draw()
