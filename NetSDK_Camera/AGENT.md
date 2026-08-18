# Dahua NetSDK Control Center — Agent Guide

Tài liệu này dành cho AI/agent làm việc với codebase này.
Đọc trước khi sửa bất kỳ file UI nào.

---

## 1. Cấu trúc project

```
launcher.py          # Main entry point — app shell, launch logic
bridge.py            # QObject bridge: signals (Python→JS) + slots (JS→Python)
theme.py             # MỌI màu sắc, font, QSS — import từ đây, KHÔNG hardcode
Demo/
  SearchDeviceDemo/  # Mỗi demo là 1 folder riêng
  RealPlayDemo/
  ...
ui/                  # Toàn bộ giao diện web (QWebEngineView)
  index.html         # HTML shell — load CSS + JS
  css/
    theme.css        # CSS custom properties: dark + light theme vars
    base.css         # Reset, scrollbar, html/body
    layout.css       # Khung: sidebar, topbar, hero, scroll-area, statusbar
    components.css   # Components: card, chip, btn, empty-state, animations
  js/
    app.js           # Logic: render cards, search, filter, bridge events
AGENT.md             # File này
REFACTOR_NOTE.md     # Ghi chú kiến trúc WebEngine refactor
```

**Quy tắc CSS:** Khi thêm style mới, đặt vào đúng file:
- Biến màu / theme → `css/theme.css`
- Style html/body, reset → `css/base.css`
- Bố cục khung (layout) → `css/layout.css`
- Component UI (card, button, chip, ...) → `css/components.css`

**Rule tuyệt đối:** Mọi màu sắc, font, spacing constant phải lấy từ `theme.py`.
Không được viết hex color thẳng vào file UI nào khác.

---

## 2. Import theme

```python
from theme import T, GLOBAL_QSS, make_shadow, font, font_mono
from theme import qss_card, qss_btn_primary, qss_btn_ghost, qss_btn_danger, qss_chip, qss_nav_item
```

---

## 3. Palette chính

### Backgrounds (từ tối → sáng)

| Token | Hex | Dùng cho |
|---|---|---|
| `T.SIDEBAR` | `#060D19` | Sidebar background |
| `T.BG` | `#07111F` | Root app background |
| `T.TOPBAR` | `#08101E` | TopBar + StatusBar |
| `T.S1` | `#0B1828` | Inner panels, row highlights |
| `T.S2` | `#101E32` | **Card default** background |
| `T.S3` | `#152438` | Card hover, input focus |
| `T.S4` | `#1A2D48` | Card active/running |

### Borders

| Token | Hex | Dùng cho |
|---|---|---|
| `T.BD` | `#162030` | Dividers, card border mặc định |
| `T.BD2` | `#1D3050` | Input outline, medium emphasis |
| `T.BD3` | `#2A4570` | Focus ring, hover border |

### Text

| Token | Hex | Dùng cho |
|---|---|---|
| `T.P1` | `#E3EDFF` | Titles, primary labels |
| `T.P2` | `#7A96BE` | Descriptions, secondary |
| `T.P3` | `#3A5470` | Muted — meta, hints, placeholder |

### Accent / Status

| Token | Hex | Dùng cho |
|---|---|---|
| `T.ACCENT` | `#3B82F6` | Blue — primary CTA, active chip |
| `T.GREEN` | `#10B981` | Running, success, ready dot |
| `T.AMBER` | `#F59E0B` | Running demo indicator |
| `T.RED` | `#EF4444` | Error, exit danger hover |

### Category accents (per-card)

| Token | Hex | Category |
|---|---|---|
| `T.CAT_DEVICE` | `#3B82F6` | Thiết bị |
| `T.CAT_CAMERA` | `#06B6D4` | Camera (live) |
| `T.CAT_CAMERA2` | `#8B5CF6` | Camera (chụp ảnh) |
| `T.CAT_ALARM` | `#F59E0B` | Cảnh báo |
| `T.CAT_PLAYBACK` | `#A855F7` | Playback |
| `T.CAT_CONTROL` | `#64748B` | Điều khiển |
| `T.CAT_AI` | `#10B981` | AI / nhận diện |
| `T.CAT_TRAFFIC` | `#F43F5E` | Giao thông |

---

## 4. Typography

```python
from theme import font, font_mono

font(16, bold=True)   # QFont Segoe UI 16px Bold — dùng cho H1
font(12, bold=True)   # H2 / section title
font(11, bold=True)   # card title
font(9)               # body / description
font(8)               # small label, button text
font(7, bold=True)    # chip, badge, section header (ALL CAPS)
font_mono(8)          # module path, version string
```

Trên Windows dùng `Segoe UI`. Không set fallback phức tạp — PyQt5 tự fallback về Arial.

---

## 5. Sizing & spacing

| Constant | Value | Dùng cho |
|---|---|---|
| `T.RADIUS_CARD` | `18px` | Card border-radius |
| `T.RADIUS_BTN` | `10px` | Button border-radius |
| `T.RADIUS_CHIP` | `9px` | Category chip |
| `T.RADIUS_INPUT` | `10px` | Search input |
| `T.SIDEBAR_W` | `210px` | Sidebar fixed width |
| `T.CARD_W` | `282px` | Demo card width |
| `T.CARD_H` | `172px` | Demo card height |
| `T.TOPBAR_H` | `58px` | TopBar height |
| `T.STATUSBAR_H` | `36px` | StatusBar height |

Padding card nội dung: `18px` ngang, `16px` trên, `14px` dưới.
Grid spacing giữa cards: `16px`.
Sidebar padding nội dung: `20px` ngang.

---

## 6. Component patterns

### Card mới

```python
from PyQt5.QtWidgets import QFrame, QVBoxLayout
from theme import T, make_shadow, qss_card

class MyCard(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(T.CARD_W, T.CARD_H)
        self.setStyleSheet(f"MyCard {{ {qss_card()} }}")
        make_shadow(self)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 14)
        lay.setSpacing(8)
        # ... thêm widgets
```

### Button primary

```python
from theme import qss_btn_primary, T
btn = QPushButton("Mở demo")
btn.setStyleSheet(qss_btn_primary(T.ACCENT))
btn.setFont(font(8, bold=True))
btn.setFixedHeight(30)
```

### Button ghost (secondary)

```python
from theme import qss_btn_ghost
btn.setStyleSheet(qss_btn_ghost())
```

### Button danger (exit, delete)

```python
from theme import qss_btn_danger
btn.setStyleSheet(qss_btn_danger())
```

### Category chip / badge

```python
from theme import qss_chip
chip = QLabel("  AI  ")
chip.setFont(font(7, bold=True))
chip.setStyleSheet(qss_chip(T.CAT_AI))
```

### Sidebar nav item

```python
from theme import qss_nav_item
btn.setStyleSheet(qss_nav_item(active=True))   # active
btn.setStyleSheet(qss_nav_item(active=False))  # inactive
```

### Section header label (ALL CAPS)

```python
lbl = QLabel("SECTION TITLE")
lbl.setFont(font(7, bold=True))
lbl.setStyleSheet(f"color: {T.P3}; background: transparent; letter-spacing: 1px;")
```

### Divider line

```python
line = QFrame()
line.setFrameShape(QFrame.HLine)
line.setFixedHeight(1)
line.setStyleSheet(f"background: {T.BD}; border: none;")
```

---

## 7. Shadow

```python
from theme import make_shadow

make_shadow(widget)                          # default: blur=24, y=6, alpha=80
make_shadow(widget, blur=16, y_off=4, alpha=60)  # nhẹ hơn
make_shadow(widget, blur=32, y_off=8, alpha=100) # đậm hơn
```

`QGraphicsDropShadowEffect` có thể bị clip bởi parent. Để tránh: đặt padding
trên parent layout bằng ít nhất `blur/2` px.

---

## 8. Layout app shell

```
QMainWindow
└── centralWidget (QWidget, bg=T.BG)
    └── QHBoxLayout (spacing=0, margins=0)
        ├── Sidebar (fixed 210px, bg=T.SIDEBAR)
        └── right_col (QWidget, bg=T.BG)
            └── QVBoxLayout (spacing=0, margins=0)
                ├── TopBar  (fixed 58px, bg=T.TOPBAR)
                ├── HeroSection (bg=T.S1, border-bottom=T.BD)
                ├── QScrollArea (transparent)
                │   └── scroll_content (QVBoxLayout, margins=28,20,28,20, spacing=16)
                │       ├── CategoryBar
                │       ├── section label
                │       └── DemoGrid
                └── StatusBar (fixed 36px, bg=T.TOPBAR)
```

---

## 9. Launch logic — KHÔNG ĐƯỢC THAY ĐỔI

Logic launch demo ở `Launcher.launch()` trong `launcher.py`:

```python
mod = importlib.import_module(module_path)   # dynamic import
cls = getattr(mod, demo.class_name)
win = cls()

if hasattr(mod, 'wnd'):  mod.wnd = win       # một số demo dùng global wnd
if hasattr(mod, 'hwnd'): mod.hwnd = win      # một số dùng hwnd

win.setAttribute(Qt.WA_DeleteOnClose, True)
win.show()
win.destroyed.connect(callback)              # cleanup khi demo bị đóng
```

Không mock, không wrap, không thay đổi cách import module demo.

---

## 10. Responsive card grid

`DemoGrid` dùng `QGridLayout` với cột tự động tính khi resize:

```
width >= (CARD_W + 16) * 3  →  3 cột
width >= (CARD_W + 16) * 2  →  2 cột
else                         →  1 cột
```

`CARD_W = 282`, spacing = 16, nên breakpoint tại ~894px và ~596px.

---

## 11. Keyboard shortcuts

| Shortcut | Hành động |
|---|---|
| `Ctrl+F` | Focus search input |
| `Ctrl+Q` | Thoát app |
| `ESC` | Xóa search nếu đang có → thoát nếu search rỗng |
| `Enter` / click card | Mở demo |

---

## 12. Card states

| State | Trigger | Visual |
|---|---|---|
| Default | Không có gì | `S2` bg, `BD` border |
| Hover | Mouse enter | `S4` bg, `BD2` border |
| Running | Demo đang mở | `S4` bg, accent border 1.5px, badge `● RUNNING` (green) |
| Error | Import/launch lỗi | `#130A0A` bg, `RED` border, auto-clear sau 4s |

---

## 13. Icons — qtawesome (Font Awesome 5)

```
pip install qtawesome
```

Dùng helpers trong `launcher.py`:

```python
# Icon label (có background box, fallback monogram)
lbl = _make_icon_lbl("fa5s.search", "SD", accent_color, box=38, icon_size=18)

# Gán icon cho QPushButton
_set_btn_icon(btn, "fa5s.folder-open", T.P2, size=13)

# Lấy QIcon thô
ico = _qta_icon("fa5s.play", color, size=16)  # returns None nếu qta chưa cài
```

**Quy tắc icon:**
- Mọi icon phải qua `_make_icon_lbl()` hoặc `_set_btn_icon()` — không gọi `qta.icon()` trực tiếp trong class code
- Luôn cung cấp `icon_fb` (monogram 2 ký tự) làm fallback khi qtawesome chưa cài
- Size chuẩn: card icon = 18px, sidebar nav = 13px, small button = 12px, stat chip = 14px
- Icon key format: `"fa5s.<name>"` (Font Awesome 5 Solid) — xem tên tại fontawesome.com

**Icon keys hay dùng:**

| Key | Dùng cho |
|---|---|
| `fa5s.search` | Tìm kiếm |
| `fa5s.video` | Camera live |
| `fa5s.camera` | Chụp ảnh |
| `fa5s.bell` | Cảnh báo |
| `fa5s.play-circle` | Playback |
| `fa5s.sliders-h` | Điều khiển |
| `fa5s.user-circle` | Face/AI |
| `fa5s.road` | Giao thông |
| `fa5s.th-large` | Dashboard/All |
| `fa5s.folder-open` | Thư mục |
| `fa5s.power-off` | Thoát |
| `fa5s.sync-alt` | Refresh |
| `fa5s.cog` | Settings |
| `fa5s.book` | Tài liệu |
| `fa5s.cubes` | Tổng số |
| `fa5s.desktop` | Platform |
| `fa5s.code` | SDK/Code |

---

## 14. Do / Don't

**DO:**
- Import màu từ `theme.py`
- Dùng `qss_*` helper functions cho button/card/chip style
- Dùng `_make_icon_lbl()` và `_set_btn_icon()` cho mọi icon
- Cung cấp fallback monogram 2 ký tự cho mọi `_make_icon_lbl()` call
- Giữ `setContentsMargins` nhất quán (card: 18/16/18/14)
- Đặt `setCursor(Qt.PointingHandCursor)` cho mọi clickable widget

**DON'T:**
- **TUYET DOI KHONG DUNG EMOJI** trong bất kỳ text, placeholder, label, button nào
- Hardcode hex color trong file UI
- Dùng `setFixedWidth` cho main window
- Viết QSS inline phức tạp lặp lại — thêm vào `qss_*` trong `theme.py`
- Gọi `qta.icon()` trực tiếp ngoài các helper functions
- Dùng gradient hay glassmorphism nặng — keep it subtle
- Đặt nhiều hơn 1 `QGraphicsDropShadowEffect` per widget
