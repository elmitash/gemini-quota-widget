# ✦ Antigravity Quota Widget

A minimalist, frameless floating desktop widget for Linux (KDE Plasma Wayland / X11) that tracks **Google Antigravity** model quotas in real time.

---

## 🌟 Overview

Unlike tools that rely on local disk logs (which miss usage from secondary laptops or other devices), **Antigravity Quota Widget** queries the running Antigravity IDE's local language server RPC (`RetrieveUserQuotaSummary`). It visualizes the **exact same real-time server-side quota** shown in Antigravity's official Model Quota UI across all your devices.

```text
┌────────────────────────────────────────────────────────┐
│ ✦ Antigravity  [PRO] [Gemini]                 🔄 📌 ✕  │
│                                                        │
│ WEEKLY LIMIT REMAINING                           30.3% │
│ [■■■■■■□□□□□□□□□□□□□□]                                 │
│ Remaining: 30.3% (Used 69.7%)        Resets in 2d 18h  │
│                                                        │
│ FIVE-HOUR LIMIT REMAINING                        56.9% │
│ [■■■■■■■■■■■□□□□□□□□□]                                 │
│ Remaining: 56.9% (Used 43.1%)       Resets in 02:24:12 │
└────────────────────────────────────────────────────────┘
```

---

## ✨ Features

- **Accurate Global Quota**: Direct ConnectRPC integration reflecting your global Google AI Pro / Ultra quota, shared across laptops and desktops.
- **Dual Limit Gauges**:
  - **Weekly Limit Remaining (%)**: Tracks long-term weekly quota with reset countdown.
  - **Five-Hour Limit Remaining (%)**: Tracks the 5-hour smoothing demand window with rolling countdown.
- **KDE Plasma & Wayland Optimized**:
  - Frameless dark translucent glass card styling.
  - Smooth window dragging (`startSystemMove` support on Wayland).
  - Reliable **Always on Top** (`📌` pin button & context menu toggle).
- **Model Group Switching**: Toggle between `Gemini Models` and `Claude and GPT models` via right-click context menu.
- **Zero API Key Setup**: Automatically discovers local `language_server` port and CSRF token from `/proc` and `ss`.
- **Privacy & Lightweight**: Pure local IPC, no external network requests, negligible CPU and memory footprint.

---

## 🛠️ Requirements

- **Linux** (Tested on CachyOS / Arch Linux, Ubuntu, Fedora)
- **Python** 3.10+
- **PyQt6**
- Running **Google Antigravity IDE**

---

## 🚀 Installation & Running

### 1. Clone the repository
```bash
git clone https://github.com/elmitash/gemini-quota-widget.git
cd gemini-quota-widget
```

### 2. Install dependencies

**Arch Linux / CachyOS**:
```bash
sudo pacman -S python-pyqt6
```

**Ubuntu / Debian**:
```bash
sudo apt install python3-pyqt6
```

**Fedora**:
```bash
sudo dnf install python3-pyqt6
```

**Or via pip / virtualenv**:
```bash
pip install -r requirements.txt
```

### 3. Run the widget
```bash
chmod +x main.py
./main.py
```

### 4. Register as Desktop App (KDE / KRunner / Kickoff)
Register the widget with its custom vector icon in your system application menu and KRunner (`Alt` + `Space`):
```bash
./install-desktop.sh
```

---

## ⚙️ Configuration (`config.json`)

The widget automatically persists its state to `config.json`:

```json
{
  "always_on_top": true,
  "window_x": 120,
  "window_y": 80,
  "poll_interval_seconds": 15,
  "target_group": "Gemini Models"
}
```

| Key | Default | Description |
| :--- | :--- | :--- |
| `always_on_top` | `true` | Keeps widget floating above other windows |
| `window_x`, `window_y` | `120`, `80` | Saved desktop screen coordinates |
| `poll_interval_seconds` | `15` | Background sync interval in seconds |
| `target_group` | `"Gemini Models"` | Target quota group (`Gemini Models` or `Claude and GPT models`) |

---

## 🖱️ Controls & Shortcuts

- **Left-Click Drag**: Move the widget anywhere on your desktop.
- **🔄 Button**: Manually trigger immediate quota refresh.
- **📌 / 📍 Button**: Toggle Always on Top.
- **✕ Button**: Close the widget.
- **Right-Click Context Menu**:
  - `🔄 Sync Now`
  - `Always on Top` toggle
  - `Switch Model Group (Gemini ↔ Claude/GPT)`
  - `Quit`

---

## 🔄 Autostart with KDE Plasma / Desktop Login

To have the widget automatically launch on system login:

```bash
mkdir -p ~/.config/autostart
cat << 'AUTOLABEL' > ~/.config/autostart/antigravity-quota-widget.desktop
[Desktop Entry]
Type=Application
Name=Antigravity Quota Widget
Exec=/usr/bin/python3 /path/to/gemini-quota-widget/main.py
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
Comment=Google Antigravity Quota Monitor
AUTOLABEL
```
*(Replace `/path/to/gemini-quota-widget` with your actual installation directory)*

---

## 📄 License

This project is open-source under the [MIT License](LICENSE).
