#!/usr/bin/env python3
"""Antigravity Model Quota Tracker (Weekly & 5-Hour Limit Monitor).

Floating desktop widget for CachyOS / KDE Plasma (PyQt6).
Directly connects to local language_server RetrieveUserQuotaSummary RPC.
Displays the EXACT same Weekly (31%) and 5-Hour (62%) limits shown in Antigravity's official UI.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtCore import QPoint, Qt, QTimer
from PyQt6.QtGui import QAction, QColor, QCursor, QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QMenu,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from quota_tracker import QuotaTracker


class GeminiQuotaWidget(QWidget):
    """구글 Antigravity 공식 Model Quota UI와 100% 동일한 주간/5시간 한도를 표시하는 플로팅 위젯."""

    def __init__(self, tracker: QuotaTracker) -> None:
        super().__init__()
        self.tracker = tracker
        self.drag_position = QPoint()
        self.is_dragging = False

        self.init_window_flags()
        self.init_ui()
        self.apply_styles()
        self.restore_position()
        self.update_display()
        self.adjustSize()

        # 1초 주기로 카운트다운 갱신
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.on_timer_tick)
        self.timer.start()

        # 15초 주기 백그라운드 자동 갱신
        poll_sec = max(5, int(self.tracker.config.get("poll_interval_seconds", 15)))
        self.sync_timer = QTimer(self)
        self.sync_timer.setInterval(poll_sec * 1000)
        self.sync_timer.timeout.connect(self.on_sync_timer_tick)
        self.sync_timer.start()

    def init_window_flags(self) -> None:
        """KDE Plasma (Wayland / X11)에서 항상 위가 안정적으로 유지되는 탑레벨 Window 플래그를 설정합니다."""
        flags = Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint
        if self.tracker.config.get("always_on_top", True):
            flags |= Qt.WindowType.WindowStaysOnTopHint

        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def init_ui(self) -> None:
        """위젯 레이아웃과 UI 컴포넌트를 초기화합니다."""
        self.setMinimumWidth(340)
        self.setMaximumWidth(360)

        self.card = QWidget(self)
        self.card.setObjectName("widgetCard")

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setColor(QColor(0, 0, 0, 160))
        shadow.setOffset(0, 6)
        self.card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(18, 14, 18, 16)
        card_layout.setSpacing(10)

        # 1. 헤더 바 (타이틀, 티어 뱃지, 그룹 뱃지, 새로고침, 핀, 닫기)
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(5)

        self.title_label = QLabel("✦ Antigravity", self.card)
        self.title_label.setObjectName("titleLabel")

        self.badge_tier = QLabel("PRO", self.card)
        self.badge_tier.setObjectName("tierBadge")
        self.badge_tier.setToolTip("Google AI Pro 요금제")

        self.badge_group = QLabel("Gemini", self.card)
        self.badge_group.setObjectName("groupBadge")

        self.btn_sync = QPushButton("🔄", self.card)
        self.btn_sync.setObjectName("iconBtn")
        self.btn_sync.setToolTip("구글 서버 최신 쿼터 즉시 동기화")
        self.btn_sync.setFixedSize(24, 24)
        self.btn_sync.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_sync.clicked.connect(self.trigger_sync)

        self.btn_pin = QPushButton("📌", self.card)
        self.btn_pin.setObjectName("iconBtn")
        self.btn_pin.setToolTip("항상 위에 표시 (클릭하여 켜기/끄기)")
        self.btn_pin.setFixedSize(24, 24)
        self.btn_pin.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_pin.clicked.connect(self.toggle_always_on_top)

        self.btn_close = QPushButton("✕", self.card)
        self.btn_close.setObjectName("closeBtn")
        self.btn_close.setToolTip("위젯 닫기")
        self.btn_close.setFixedSize(24, 24)
        self.btn_close.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_close.clicked.connect(self.close)

        header_layout.addWidget(self.title_label)
        header_layout.addWidget(self.badge_tier)
        header_layout.addWidget(self.badge_group)
        header_layout.addStretch()
        header_layout.addWidget(self.btn_sync)
        header_layout.addWidget(self.btn_pin)
        header_layout.addWidget(self.btn_close)
        card_layout.addLayout(header_layout)


        # 3. 주간 남은 한도 (Weekly Limit Remaining) 섹션 - 상단 배치
        weekly_box = QVBoxLayout()
        weekly_box.setSpacing(4)

        weekly_header = QHBoxLayout()
        self.lbl_weekly_title = QLabel("WEEKLY LIMIT REMAINING", self.card)
        self.lbl_weekly_title.setObjectName("sectionSubTitle")
        self.lbl_weekly_pct = QLabel("100.0%", self.card)
        self.lbl_weekly_pct.setObjectName("pctLabel")
        weekly_header.addWidget(self.lbl_weekly_title)
        weekly_header.addStretch()
        weekly_header.addWidget(self.lbl_weekly_pct)
        weekly_box.addLayout(weekly_header)

        self.bar_weekly = QProgressBar(self.card)
        self.bar_weekly.setObjectName("weeklyProgressBar")
        self.bar_weekly.setTextVisible(False)
        self.bar_weekly.setFixedHeight(8)
        self.bar_weekly.setRange(0, 1000)
        weekly_box.addWidget(self.bar_weekly)

        weekly_stats = QHBoxLayout()
        self.lbl_weekly_detail = QLabel("Remaining: 100.0%", self.card)
        self.lbl_weekly_detail.setObjectName("statsHighlight")
        self.lbl_weekly_reset = QLabel("Resets in --", self.card)
        self.lbl_weekly_reset.setObjectName("statsText")
        weekly_stats.addWidget(self.lbl_weekly_detail)
        weekly_stats.addStretch()
        weekly_stats.addWidget(self.lbl_weekly_reset)
        weekly_box.addLayout(weekly_stats)

        card_layout.addLayout(weekly_box)

        # 4. 5시간/일간 남은 한도 (Five Hour Limit Remaining) 섹션 - 하단 배치
        short_box = QVBoxLayout()
        short_box.setSpacing(4)

        short_header = QHBoxLayout()
        self.lbl_short_title = QLabel("FIVE-HOUR LIMIT REMAINING", self.card)
        self.lbl_short_title.setObjectName("sectionSubTitle")
        self.lbl_short_pct = QLabel("100.0%", self.card)
        self.lbl_short_pct.setObjectName("pctLabel")
        short_header.addWidget(self.lbl_short_title)
        short_header.addStretch()
        short_header.addWidget(self.lbl_short_pct)
        short_box.addLayout(short_header)

        self.bar_short = QProgressBar(self.card)
        self.bar_short.setObjectName("shortProgressBar")
        self.bar_short.setTextVisible(False)
        self.bar_short.setFixedHeight(8)
        self.bar_short.setRange(0, 1000)
        short_box.addWidget(self.bar_short)

        short_stats = QHBoxLayout()
        self.lbl_short_detail = QLabel("Remaining: 100.0%", self.card)
        self.lbl_short_detail.setObjectName("statsHighlight")
        self.lbl_short_reset = QLabel("Resets in --", self.card)
        self.lbl_short_reset.setObjectName("statsText")
        short_stats.addWidget(self.lbl_short_detail)
        short_stats.addStretch()
        short_stats.addWidget(self.lbl_short_reset)
        short_box.addLayout(short_stats)

        card_layout.addLayout(short_box)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.addWidget(self.card)

    def apply_styles(self) -> None:
        """KDE Plasma 맞춤형 반투명 다크 QSS 스타일시트를 적용합니다."""
        self.setStyleSheet("""
            QWidget {
                font-family: 'Noto Sans', 'Segoe UI', 'Ubuntu', sans-serif;
            }
            #widgetCard {
                background-color: rgba(20, 22, 30, 0.92);
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 16px;
            }
            #titleLabel {
                color: #e2e8f0;
                font-size: 12px;
                font-weight: 700;
                letter-spacing: 0.5px;
            }
            #tierBadge {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #f59e0b, stop:1 #eab308);
                color: #0f172a;
                border-radius: 5px;
                font-size: 9px;
                font-weight: 900;
                padding: 1px 5px;
                letter-spacing: 0.5px;
            }
            #groupBadge {
                background-color: rgba(56, 189, 248, 0.15);
                color: #38bdf8;
                border: 1px solid rgba(56, 189, 248, 0.3);
                border-radius: 6px;
                font-size: 10px;
                font-weight: 700;
                padding: 1px 6px;
            }
            #sectionSubTitle {
                color: #94a3b8;
                font-size: 9px;
                font-weight: 700;
                letter-spacing: 0.8px;
            }
            #pctLabel {
                font-size: 12px;
                font-weight: 800;
                font-family: 'JetBrains Mono', monospace;
            }
            #weeklyProgressBar, #shortProgressBar {
                background-color: rgba(255, 255, 255, 0.08);
                border: none;
                border-radius: 4px;
            }
            #statsHighlight {
                color: #e2e8f0;
                font-size: 10px;
                font-weight: 600;
                font-family: 'JetBrains Mono', monospace;
            }
            #statsText {
                color: #94a3b8;
                font-size: 10px;
                font-weight: 500;
            }
            QPushButton#iconBtn, QPushButton#closeBtn {
                background-color: transparent;
                border: none;
                border-radius: 6px;
                color: #94a3b8;
                font-size: 12px;
            }
            QPushButton#iconBtn:hover {
                background-color: rgba(255, 255, 255, 0.1);
                color: #ffffff;
            }
            QPushButton#closeBtn:hover {
                background-color: rgba(239, 68, 68, 0.25);
                color: #ef4444;
            }
            QMenu {
                background-color: #1a1e28;
                color: #e2e8f0;
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 8px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 18px;
                border-radius: 4px;
                font-size: 11px;
            }
            QMenu::item:selected {
                background-color: #2563eb;
                color: #ffffff;
            }
            QMenu::separator {
                height: 1px;
                background-color: rgba(255, 255, 255, 0.1);
                margin: 4px 6px;
            }
        """)

    def update_display(self) -> None:
        """구글 Antigravity 공식 UI와 100% 동일한 쿼터 데이터를 화면에 갱신합니다."""
        summary = self.tracker.get_quota_summary_data()

        # 1. 헤더 뱃지
        s = summary.short_term
        self.badge_group.setText(summary.group_name.replace(" Models", ""))
        self.badge_tier.setToolTip(f"{summary.account_email} ({summary.account_tier} Plan)")

        # 2. 주간 남은 한도 (Weekly Limit Remaining) - 상단
        w = summary.weekly
        self.lbl_weekly_pct.setText(f"{w.remaining_pct:.1f}%")
        self.lbl_weekly_detail.setText(f"Remaining: {w.remaining_pct:.1f}% (Used {w.used_pct:.1f}%)")
        self.lbl_weekly_reset.setText(f"Resets in {w.remaining_time_str}")
        self.bar_weekly.setValue(int(w.remaining_pct * 10))
        self.apply_bar_color(self.bar_weekly, self.lbl_weekly_pct, w.remaining_pct)

        # 3. 5시간/일간 남은 한도 (Five Hour Limit Remaining) - 하단
        self.lbl_short_pct.setText(f"{s.remaining_pct:.1f}%")
        self.lbl_short_detail.setText(f"Remaining: {s.remaining_pct:.1f}% (Used {s.used_pct:.1f}%)")
        self.lbl_short_reset.setText(f"Resets in {s.remaining_time_str}")
        self.bar_short.setValue(int(s.remaining_pct * 10))
        self.apply_bar_color(self.bar_short, self.lbl_short_pct, s.remaining_pct)

        self.btn_sync.setEnabled(not self.tracker.is_fetching)

        # 항상 위 핀 버튼 활성화 상태 표시
        is_pinned = bool(self.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
        self.btn_pin.setText("📌" if is_pinned else "📍")
        self.btn_pin.setStyleSheet("color: #38bdf8;" if is_pinned else "color: #64748b;")

    def apply_bar_color(self, bar: QProgressBar, label: QLabel, remaining_pct: float) -> None:
        if remaining_pct >= 40.0:
            chunk_style = "stop:0 #06b6d4, stop:1 #10b981"
            color_hex = "#10b981"
        elif remaining_pct >= 15.0:
            chunk_style = "stop:0 #f59e0b, stop:1 #d97706"
            color_hex = "#f59e0b"
        else:
            chunk_style = "stop:0 #f43f5e, stop:1 #e11d48"
            color_hex = "#f43f5e"

        label.setStyleSheet(f"color: {color_hex};")
        bar_id = bar.objectName()
        bar.setStyleSheet(f"""
            #{bar_id} {{
                background-color: rgba(255, 255, 255, 0.08);
                border: none;
                border-radius: 4px;
            }}
            #{bar_id}::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, {chunk_style});
                border-radius: 4px;
            }}
        """)

    def trigger_sync(self) -> None:
        self.tracker.trigger_rpc_async(callback=self.on_sync_finished)
        self.update_display()

    def on_sync_finished(self) -> None:
        QTimer.singleShot(0, self.update_display)

    def on_timer_tick(self) -> None:
        self.update_display()

    def on_sync_timer_tick(self) -> None:
        self.trigger_sync()

    def toggle_always_on_top(self) -> None:
        is_pinned = bool(self.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
        new_state = not is_pinned

        self.hide()
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, new_state)
        self.tracker.set_always_on_top(new_state)
        self.show()
        self.raise_()
        self.activateWindow()

        self.update_display()

    def restore_position(self) -> None:
        x = self.tracker.config.get("window_x", 120)
        y = self.tracker.config.get("window_y", 80)
        self.move(x, y)

    # -------------------------------------------------------------
    # 마우스 드래그를 통한 자유로운 창 이동
    # -------------------------------------------------------------
    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_dragging = True
            if self.windowHandle() and hasattr(self.windowHandle(), "startSystemMove"):
                if self.windowHandle().startSystemMove():
                    self.is_dragging = False
                    return

            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self.is_dragging and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self.is_dragging:
            self.is_dragging = False
            self.tracker.update_window_position(self.x(), self.y())
            event.accept()

    # -------------------------------------------------------------
    # 우클릭 컨텍스트 메뉴 (Context Menu)
    # -------------------------------------------------------------
    def contextMenuEvent(self, event) -> None:  # noqa: N802
        menu = QMenu(self)

        action_sync = menu.addAction("🔄 구글 서버 쿼터 지금 동기화 (Sync Now)")
        action_sync.triggered.connect(self.trigger_sync)

        menu.addSeparator()

        is_pinned = bool(self.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
        action_pin = QAction("항상 위에 고정 (Always on Top)", self)
        action_pin.setCheckable(True)
        action_pin.setChecked(is_pinned)
        action_pin.triggered.connect(self.toggle_always_on_top)
        menu.addAction(action_pin)

        menu.addSeparator()

        # 모델 그룹 전환 메뉴 (Gemini <-> Claude/GPT)
        action_toggle_group = menu.addAction("모델 그룹 전환 (Gemini ↔ Claude/GPT)")
        action_toggle_group.triggered.connect(self.toggle_target_group)

        menu.addSeparator()

        action_quit = menu.addAction("위젯 종료 (Quit)")
        action_quit.triggered.connect(self.close)

        menu.exec(event.globalPos())

    def toggle_target_group(self) -> None:
        curr = self.tracker.config.get("target_group", "Gemini Models")
        new_grp = "Claude and GPT models" if "gemini" in curr.lower() else "Gemini Models"
        self.tracker.config["target_group"] = new_grp
        self.tracker.save_config()
        self.update_display()

    def closeEvent(self, event) -> None:  # noqa: N802
        self.tracker.update_window_position(self.x(), self.y())
        super().closeEvent(event)


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("AntigravityOfficialQuotaTracker")
    app.setDesktopFileName("gemini-quota-widget")

    icon_path = Path(__file__).parent / "resources" / "icon.svg"
    app_icon = QIcon(str(icon_path)) if icon_path.exists() else None
    if app_icon:
        app.setWindowIcon(app_icon)

    tracker = QuotaTracker(Path(__file__).parent / "config.json")
    widget = GeminiQuotaWidget(tracker)
    if app_icon:
        widget.setWindowIcon(app_icon)
    widget.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
