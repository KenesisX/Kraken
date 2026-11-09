"""
ui.py — the touchscreen interface (smooth build).

What makes it smooth:
  * Every category page is built ONCE into a QStackedWidget. Switching tabs
    just flips the stack index — no destroy/recreate, so it's instant.
  * Kinetic scrolling is momentum-tuned (QScrollerProperties) for a native,
    phone-like flick with gentle deceleration and no jarring overshoot.
  * Tab changes cross-fade quickly (QPropertyAnimation) instead of popping.

Layout:
  ┌──────────────────────────────────────────────────────────┐
  │ STATUS BAR: host · ip · cpu · temp · batt · clock          │
  ├──────────┬─────────────────────────────────────────────────┤
  │ RAIL     │  TOOL PAGES (QStackedWidget, one per category)  │
  │ (scroll) │                                                  │
  │          ├─────────────────────────────────────────────────┤
  │          │  CONSOLE (live output)         [STOP] [CLR] [⟳]  │
  └──────────┴─────────────────────────────────────────────────┘
"""

from __future__ import annotations

import os

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication, QDialog, QFrame, QGraphicsOpacityEffect, QGridLayout,
    QHBoxLayout, QLabel, QMessageBox, QPlainTextEdit, QPushButton,
    QScrollArea, QScroller, QScrollerProperties, QStackedWidget,
    QVBoxLayout, QWidget,
)

from . import (academy, art, companion as companion_mod, config as config_mod,
               osk, profiles as profiles_mod, report as report_mod,
               signaldisplay, theme)
from .config import AppConfig, Tool
from .notify import Notifier
from .runner import CommandRunner
from .scope import ScopeGuard
from .session import SessionLogger
from .sysmon import SysMon

GRID_COLS = 2


class ConsentDialog(QDialog):
    """First-run gate. No bypass flag — you tap to accept each boot."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Authorization")
        self.setModal(True)
        lay = QVBoxLayout(self)
        msg = QLabel(
            "Strikeback X runs active network and radio tools.\n\n"
            "Use it ONLY against systems you own or have explicit, "
            "written permission to test.\n\n"
            "Unauthorized access is illegal."
        )
        msg.setWordWrap(True)
        msg.setFont(QFont("DejaVu Sans", 13))
        lay.addWidget(msg)
        row = QHBoxLayout()
        no = QPushButton("Shut down")
        no.setObjectName("Danger")
        no.clicked.connect(self.reject)
        yes = QPushButton("I am authorized")
        yes.clicked.connect(self.accept)
        row.addWidget(no)
        row.addWidget(yes)
        lay.addLayout(row)
        self.resize(460, 300)


class ConfirmPad(QDialog):
    def __init__(self, tool: Tool, resolved: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Confirm")
        self.setModal(True)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(f"Run: {tool.label}?"))
        cmd = QLabel(resolved)
        cmd.setWordWrap(True)
        cmd.setObjectName("Crumb")
        lay.addWidget(cmd)
        row = QHBoxLayout()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        go = QPushButton("Run")
        go.setObjectName("Danger")
        go.clicked.connect(self.accept)
        row.addWidget(cancel)
        row.addWidget(go)
        lay.addLayout(row)
        self.resize(460, 220)


class MainWindow(QWidget):
    def __init__(self, cfg: AppConfig, notifier: Notifier | None = None,
                 state=None):
        super().__init__()
        self.cfg = cfg
        self.runner = CommandRunner(self)
        self.sysmon = SysMon()
        self.scope = ScopeGuard(cfg.scope)
        self.session = SessionLogger(cfg.log_dir, cfg.engagement)
        self.notifier = notifier or Notifier()
        self.state = state
        self._last_label = ""
        self._low_batt_warned = False
        self._active_cat = 0
        self._tab_buttons: list[QPushButton] = []
        self._anim = None
        self._cfg_path = os.environ.get(
            "RJX_CONFIG", os.path.join(os.path.dirname(__file__), "tools.yaml"))

        self.setWindowTitle(cfg.title)
        self.setStyleSheet(theme.stylesheet())

        self._build()
        self._wire_runner()
        self._startup_banner()
        self._select_cat(0)

        self.sysmon.cpu_pct()  # prime CPU delta
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._refresh_status)
        self.timer.start(1000)
        self._refresh_status()

    # ---- construction -----------------------------------------------------

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_status_bar())

        body = QHBoxLayout()
        body.setContentsMargins(10, 10, 10, 10)
        body.setSpacing(10)
        body.addWidget(self._build_tab_rail(), 0)

        right = QVBoxLayout()
        right.setSpacing(10)
        self.title_lbl = QLabel()
        self.title_lbl.setObjectName("Title")
        right.addWidget(self.title_lbl)

        self.stack = QStackedWidget()
        right.addWidget(self.stack, 3)

        right.addWidget(self._build_console(), 2)
        body.addLayout(right, 1)
        root.addLayout(body, 1)

        self._populate_catalog()

    def _build_status_bar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("StatusBar")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(12, 6, 12, 6)
        self.lbl_host = self._stat()
        self.lbl_ip = self._stat()
        self.lbl_cpu = self._stat()
        self.lbl_temp = self._stat()
        self.lbl_batt = self._stat()
        self.lbl_quip = QLabel(art.quip())
        self.lbl_quip.setObjectName("Quip")
        self.lbl_clock = self._stat()
        for w in (self.lbl_host, self.lbl_ip, self.lbl_cpu,
                  self.lbl_temp, self.lbl_batt):
            lay.addWidget(w)
            lay.addStretch(1)
        lay.addWidget(self.lbl_quip)
        lay.addStretch(2)
        lay.addWidget(self.lbl_clock)
        bar.setFixedHeight(44)
        return bar

    def _stat(self) -> QLabel:
        lbl = QLabel("--")
        lbl.setProperty("role", "value")
        return lbl

    def _build_tab_rail(self) -> QWidget:
        self._rail = QWidget()
        self._rail_lay = QVBoxLayout(self._rail)
        self._rail_lay.setContentsMargins(0, 0, 0, 0)
        self._rail_lay.setSpacing(8)

        mascot_pm = art.mascot_pixmap(84)
        if mascot_pm is not None:
            mascot = QLabel()
            mascot.setPixmap(mascot_pm)
            mascot.setAlignment(Qt.AlignCenter)
            self._rail_lay.addWidget(mascot)

        vars_btn = QPushButton("✎\nVARS")
        vars_btn.setObjectName("Tab")
        vars_btn.clicked.connect(self._open_vars)
        self._rail_lay.addWidget(vars_btn)
        learn_btn = QPushButton("🎓\nLEARN")
        learn_btn.setObjectName("Tab")
        learn_btn.clicked.connect(self._open_academy)
        self._rail_lay.addWidget(learn_btn)
        report_btn = QPushButton("⎙\nREPORT")
        report_btn.setObjectName("Tab")
        report_btn.clicked.connect(self._open_report)
        self._rail_lay.addWidget(report_btn)
        profile_btn = QPushButton("⇅\nPROFILE")
        profile_btn.setObjectName("Tab")
        profile_btn.clicked.connect(self._open_profiles)
        self._rail_lay.addWidget(profile_btn)
        signal_btn = QPushButton("📊\nSIGNAL")
        signal_btn.setObjectName("Tab")
        signal_btn.clicked.connect(self._open_signal)
        self._rail_lay.addWidget(signal_btn)
        # category buttons get appended by _populate_catalog()

        area = QScrollArea()
        area.setWidget(self._rail)
        area.setWidgetResizable(True)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        area.setFrameShape(QFrame.NoFrame)
        area.setFixedWidth(118)
        self._touch_scroll(area)
        return area

    @staticmethod
    def _touch_scroll(area: QScrollArea) -> None:
        """Momentum finger-scroll; a quick tap still clicks through."""
        try:
            vp = area.viewport()
            QScroller.grabGesture(vp, QScroller.LeftMouseButtonGesture)
            sc = QScroller.scroller(vp)
            props = sc.scrollerProperties()
            P = QScrollerProperties
            props.setScrollMetric(P.DragVelocitySmoothingFactor, 0.6)
            props.setScrollMetric(P.DecelerationFactor, 0.28)
            props.setScrollMetric(P.MinimumVelocity, 0.0)
            props.setScrollMetric(P.OvershootDragResistanceFactor, 0.45)
            props.setScrollMetric(P.OvershootScrollDistanceFactor, 0.18)
            props.setScrollMetric(P.VerticalOvershootPolicy,
                                  P.OvershootWhenScrollable)
            sc.setScrollerProperties(props)
        except Exception:
            pass

    def _make_page(self, cat) -> QScrollArea:
        host = QWidget()
        grid = QGridLayout(host)
        grid.setSpacing(10)
        grid.setContentsMargins(0, 0, 6, 0)
        grid.setAlignment(Qt.AlignTop)
        for i, tool in enumerate(cat.tools):
            b = QPushButton(("⚠ " if tool.confirm else "") + tool.label)
            b.setObjectName("Tool")
            if tool.desc:
                b.setToolTip(tool.desc)
            b.clicked.connect(lambda _=False, t=tool: self._launch(t))
            grid.addWidget(b, i // GRID_COLS, i % GRID_COLS)
        area = QScrollArea()
        area.setWidget(host)
        area.setWidgetResizable(True)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        area.setFrameShape(QFrame.NoFrame)
        self._touch_scroll(area)
        return area

    def _populate_catalog(self) -> None:
        """(Re)build the tab buttons + stacked pages from cfg.categories."""
        for b in self._tab_buttons:
            b.deleteLater()
        self._tab_buttons.clear()
        while self.stack.count():
            w = self.stack.widget(0)
            self.stack.removeWidget(w)
            w.deleteLater()

        for i, cat in enumerate(self.cfg.categories):
            tab = QPushButton(f"{cat.icon}\n{cat.name}")
            tab.setObjectName("Tab")
            tab.setProperty("active", False)
            tab.clicked.connect(lambda _=False, idx=i: self._select_cat(idx))
            self._tab_buttons.append(tab)
            self._rail_lay.addWidget(tab)
            self.stack.addWidget(self._make_page(cat))

    def _build_console(self) -> QWidget:
        wrap = QWidget()
        lay = QVBoxLayout(wrap)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        self.console = QPlainTextEdit()
        self.console.setReadOnly(True)
        self.console.setMaximumBlockCount(5000)
        self.console.setCenterOnScroll(True)
        lay.addWidget(self.console, 1)

        ctl = QHBoxLayout()
        self.lbl_crumb = QLabel("idle")
        self.lbl_crumb.setObjectName("Crumb")
        ctl.addWidget(self.lbl_crumb, 1)

        self.btn_stop = QPushButton("■ Stop")
        self.btn_stop.setObjectName("Danger")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.runner.stop)

        btn_clear = QPushButton("Clear")
        btn_clear.setObjectName("Ctrl")
        btn_clear.clicked.connect(self.console.clear)

        btn_reload = QPushButton("⟳")
        btn_reload.setObjectName("Ctrl")
        btn_reload.clicked.connect(self._reload_cfg)

        ctl.addWidget(self.btn_stop)
        ctl.addWidget(btn_clear)
        ctl.addWidget(btn_reload)
        lay.addLayout(ctl)
        return wrap

    # ---- behaviour --------------------------------------------------------

    def _select_cat(self, idx: int) -> None:
        if idx < 0 or idx >= self.stack.count():
            return
        self._active_cat = idx
        for i, b in enumerate(self._tab_buttons):
            b.setProperty("active", i == idx)
            b.style().unpolish(b)
            b.style().polish(b)
        cat = self.cfg.categories[idx]
        self.title_lbl.setText(f"{cat.icon}  {cat.name}")
        self.stack.setCurrentIndex(idx)
        self._fade_in(self.stack.currentWidget())

    def _fade_in(self, w: QWidget) -> None:
        try:
            eff = QGraphicsOpacityEffect(w)
            w.setGraphicsEffect(eff)
            anim = QPropertyAnimation(eff, b"opacity", self)
            anim.setDuration(130)
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            anim.setEasingCurve(QEasingCurve.OutCubic)
            anim.finished.connect(lambda: w.setGraphicsEffect(None))
            anim.start(QPropertyAnimation.DeleteWhenStopped)
            self._anim = anim
        except Exception:
            pass

    def _open_vars(self) -> None:
        dlg = osk.VarsEditor(self.cfg.variables, self)
        if dlg.exec() == QDialog.Accepted:
            self.cfg.variables = dlg.result_vars()
            ok = config_mod.save_overrides(self.cfg.variables)
            self._append("[=] Variables updated"
                         + ("" if ok else " (not persisted — check ~/.config)") + ".\n")

    def _open_academy(self) -> None:
        dlg = academy.AcademyDialog(self.cfg.variables, self._run_raw, self)
        dlg.exec()

    def _open_signal(self) -> None:
        dlg = signaldisplay.SignalDisplayDialog(self.cfg.variables, self._run_raw, self)
        dlg.exec()

    def _open_report(self) -> None:
        try:
            out = report_mod.generate(self.session.folder, self.sysmon.hostname())
            s = out["stats"]
            self._append(
                f"[=] Report written ({s['total']} cmds, {s['ok']} ok, "
                f"{len(s['blocked'])} blocked):\n  {out['md']}\n  {out['html']}\n"
                + (f"  {out['pdf']}\n" if out.get("pdf") else
                   "  (install wkhtmltopdf for PDF, or open the HTML and Print→PDF)\n"))
            self.notifier.push("⎙ Report ready", os.path.basename(out["html"]),
                               tags=["page_facing_up"])
        except Exception as e:
            self._append(f"[!] Report failed: {e}\n")

    def _open_profiles(self) -> None:
        dlg = profiles_mod.ProfileDialog(self._cfg_path, self)
        if dlg.exec() == QDialog.Accepted and dlg.chosen:
            self._load_profile(dlg.chosen)

    def _load_profile(self, path: str) -> None:
        from .config import load
        try:
            self.cfg = load(path)
            self._cfg_path = path
            self.scope = ScopeGuard(self.cfg.scope)
            self._populate_catalog()
            self._select_cat(0)
            self._append(f"[=] Profile loaded: {os.path.basename(path)} "
                         f"({len(self.cfg.categories)} tabs, engagement "
                         f"'{self.cfg.engagement}').\n")
        except Exception as e:
            self._append(f"[!] Profile load failed: {e}\n")

    def _run_raw(self, resolved: str, label: str) -> None:
        """Run an Academy command: scope-checked, confirmed, logged."""
        if self.runner.running:
            self._append("[!] Busy — stop the current command first.\n")
            return
        verdict = self.scope.check(resolved)
        if not verdict.allowed:
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Critical)
            box.setWindowTitle("Out of scope")
            box.setText("⛔ " + verdict.reason)
            run_btn = box.addButton("Override & run", QMessageBox.DestructiveRole)
            box.addButton("Cancel", QMessageBox.RejectRole)
            box.exec()
            if box.clickedButton() is not run_btn:
                self.session.blocked(label, resolved, verdict.reason)
                self._append(f"[⛔] Blocked: {verdict.reason}\n")
                return
        if QMessageBox.question(self, "Run command", resolved) != QMessageBox.Yes:
            return
        self.console.clear()
        self._append(f"$ {resolved}\n")
        self._last_label = label
        self.session.start_command(label, resolved, in_scope=verdict.allowed)
        self.notifier.push(f"▶ {label}", resolved, actions=[self.notifier.stop_action()])
        self.runner.start(resolved, shell=True)

    def _launch(self, tool: Tool) -> None:
        if self.runner.running:
            self._append("[!] Busy — stop the current command first.\n")
            return
        resolved = self.cfg.expand(tool.cmd)

        verdict = self.scope.check(resolved)
        override = False
        if not verdict.allowed:
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Critical)
            box.setWindowTitle("Out of scope")
            box.setText("⛔ " + verdict.reason)
            box.setInformativeText(
                f"Authorized scope: {self.scope.describe()}\n\n"
                "Run anyway only if you have confirmed authorization."
            )
            run_btn = box.addButton("Override & run", QMessageBox.DestructiveRole)
            box.addButton("Cancel", QMessageBox.RejectRole)
            box.exec()
            if box.clickedButton() is not run_btn:
                self.session.blocked(tool.label, resolved, verdict.reason)
                self._append(f"[⛔] Blocked: {verdict.reason}\n")
                self.notifier.push("⛔ Out of scope", f"{tool.label}: {verdict.reason}",
                                   tags=["no_entry"], priority="high")
                return
            override = True

        if tool.confirm:
            if ConfirmPad(tool, resolved, self).exec() != QDialog.Accepted:
                return

        self.console.clear()
        tag = "  [SCOPE OVERRIDE]" if override else ""
        self._append(f"$ {resolved}{tag}\n")
        self._last_label = tool.label
        self.session.start_command(tool.label, resolved, in_scope=not override)
        self.notifier.push(f"▶ {tool.label}", resolved, tags=["fox_face"],
                           actions=[self.notifier.stop_action()])
        self.runner.start(resolved, shell=tool.shell)

    def _reload_cfg(self) -> None:
        from .config import load
        try:
            self.cfg = load(self._cfg_path)
            self.scope = ScopeGuard(self.cfg.scope)
            self._populate_catalog()
            self._select_cat(0)
            self._append("[=] Config reloaded — tabs and tools refreshed.\n")
        except Exception as e:
            self._append(f"[!] Reload failed: {e}\n")

    def _wire_runner(self) -> None:
        self.runner.output.connect(self._append)
        self.runner.output.connect(self.session.write_output)
        self.runner.started.connect(lambda c: self.lbl_crumb.setText("running…"))
        self.runner.finished.connect(lambda c: self.lbl_crumb.setText(f"done ({c})"))
        self.runner.finished.connect(self.session.end_command)
        self.runner.finished.connect(self._notify_finished)
        self.runner.state_changed.connect(self._on_run_state)

    def _notify_finished(self, code: int) -> None:
        tag = "white_check_mark" if code == 0 else "warning"
        self.notifier.push(f"✔ {self._last_label or 'command'}",
                           f"exit {code}", tags=[tag])

    def _on_run_state(self, running: bool) -> None:
        self.btn_stop.setEnabled(running)
        self.stack.setEnabled(not running)

    def _append(self, text: str) -> None:
        sb = self.console.verticalScrollBar()
        at_bottom = sb.value() >= sb.maximum() - 4
        self.console.moveCursor(self.console.textCursor().End)
        self.console.insertPlainText(text)
        if at_bottom:
            sb.setValue(sb.maximum())

    def _startup_banner(self) -> None:
        self._append(
            f"Strikeback X  ·  engagement: {self.cfg.engagement}\n"
            f"Scope guard : {self.scope.describe()}\n"
            f"Loot folder : {self.session.folder}\n"
            f"Select a category and tap a tool. Output streams here.\n"
            "----------------------------------------------------------\n"
        )

    def _refresh_status(self) -> None:
        t = self.sysmon.sample()
        self._tick = getattr(self, "_tick", 0) + 1
        if self._tick % 6 == 1:
            self.lbl_quip.setText(art.quip())

        if self.state is not None:
            first_ip = next(iter(t.ips.items()), (None, None))[1]
            self.state.set_status({
                "engagement": self.cfg.engagement,
                "scope": self.scope.describe(),
                "running": self.runner.running,
                "current": self._last_label if self.runner.running else "",
                "ip": first_ip, "cpu": None if t.cpu_pct is None else round(t.cpu_pct),
                "temp": None if t.temp_c is None else round(t.temp_c),
                "batt": None if t.battery_pct is None else round(t.battery_pct),
            })
            if self.state.stop_event.is_set():
                self.state.stop_event.clear()
                if self.runner.running:
                    self._append("\n[watch] remote Stop received.\n")
                    self.runner.stop()

        if (t.battery_pct is not None and t.battery_pct < 15
                and not t.charging and not self._low_batt_warned):
            self._low_batt_warned = True
            self.notifier.push("🔋 Low battery", f"{t.battery_pct:.0f}% — wrap up",
                               tags=["battery"], priority="high")
        if t.charging:
            self._low_batt_warned = False

        self.lbl_host.setText(f"🖥 {t.hostname}")
        if t.ips:
            first = next(iter(t.ips.items()))
            extra = f" +{len(t.ips)-1}" if len(t.ips) > 1 else ""
            self.lbl_ip.setText(f"🌐 {first[0]}:{first[1]}{extra}")
        else:
            self.lbl_ip.setText("🌐 no-link")
        self.lbl_cpu.setText(f"⚡ {t.cpu_pct:.0f}%" if t.cpu_pct is not None else "⚡ --")
        if t.temp_c is not None:
            glyph = "🔥" if t.temp_c >= 75 else "🌡"
            self.lbl_temp.setText(f"{glyph} {t.temp_c:.0f}°C")
        else:
            self.lbl_temp.setText("🌡 --")
        if t.battery_pct is not None:
            chg = "⚡" if t.charging else ""
            self.lbl_batt.setText(f"🔋{chg} {t.battery_pct:.0f}%")
        else:
            self.lbl_batt.setText("🔌 ext")
        self.lbl_clock.setText(t.clock)


def run(cfg: AppConfig, fullscreen: bool = True) -> int:
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(theme.stylesheet())
    splash = None
    try:
        splash = art.make_splash()
        art.hold_splash(app, splash, 1.1)
    except Exception:
        splash = None
    if splash is not None:
        splash.close()
    if cfg.require_consent:
        if ConsentDialog().exec() != QDialog.Accepted:
            return 0

    # first-run setup wizard (only when nothing has been saved yet)
    if not config_mod.overrides_exist():
        try:
            from . import wizard
            wizard.SetupWizard(cfg).exec()
        except Exception:
            pass

    state = companion_mod.CompanionState()
    companion_mod.start(cfg, state)
    nc = cfg.notify or {}
    notifier = Notifier(
        server=nc.get("ntfy_server", "https://ntfy.sh"),
        topic=nc.get("topic", ""),
        token=(cfg.companion or {}).get("token", ""),
        public_url=nc.get("public_url", ""),
        priority=nc.get("priority", "default"),
    )

    win = MainWindow(cfg, notifier=notifier, state=state)
    if fullscreen:
        win.showFullScreen()
    else:
        win.resize(800, 480)
        win.show()
    return app.exec()
