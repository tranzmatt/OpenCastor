# OpenCastor Brand Assets

## ⚡ Primary Source — `brand/transparent/`

**Always use files from `brand/transparent/` for logos, favicons, PWA icons, and app assets.**
This is the canonical, production-ready set. Transparent background, works on any surface.

| File | Size | Use |
|---|---|---|
| `transparent/icon-transparent.svg` | vector | **The master icon** — transparent bg, scales to any size |
| `transparent/icon-64.png` | 64×64 | Favicon (`web/favicon.png`), small UI elements |
| `transparent/icon-128.png` | 128×128 | App thumbnails, login screens, docs |
| `transparent/icon-192.png` | 192×192 | PWA manifest (`Icon-192.png`), Android |
| `transparent/icon-256.png` | 256×256 | macOS Dock, Windows taskbar |
| `transparent/icon-512.png` | 512×512 | App stores, high-DPI, PWA splash |
| `transparent/icon-1024.png` | 1024×1024 | Print, press kit, App Store submission |
| `transparent/android-chrome-192.png` | 192×192 | PWA manifest maskable icon (192) |
| `transparent/android-chrome-512.png` | 512×512 | PWA manifest maskable icon (512) |
| `transparent/apple-touch-icon.png` | 180×180 | iOS home screen |
| `transparent/favicon.ico` | multi | Legacy `.ico` favicon |

## Dark-background variant — `brand/inverse/`

Use `brand/inverse/` when placing the logo on dark/colored backgrounds where the
transparent icon would be hard to see (e.g. dark headers, colored cards).

| File | Use |
|---|---|
| `inverse/icon-inverse.svg` | White/light icon on transparent bg — dark headers |
| `inverse/icon-*.png` | Pre-rendered inverse PNGs at each size |

> `website/public/assets/logo-white.svg` → sourced from `brand/inverse/icon-inverse.svg`

## Full lockup (icon + wordmark)

| File | Use |
|---|---|
| `lockup.svg` | Horizontal lockup — light backgrounds |
| `lockup-1200x400.png` | OG image, GitHub social card, LinkedIn |
| `banner-1500x500.png` | Twitter/X banner |

## Root `brand/` files

Root-level PNGs (`brand/icon-*.png`, `brand/android-chrome-*.png` etc.) have
**solid/colored backgrounds** — not transparent. Do not use these as app icons or favicons.
They exist as source exports for specific print/marketing contexts.

---

## Where each file is used

| Asset location | Source file |
|---|---|
| `website/public/favicon.png` | `brand/transparent/icon-64.png` |
| `website/public/favicon.svg` | `brand/transparent/icon-transparent.svg` |
| `website/public/assets/logo.svg` | `brand/transparent/icon-transparent.svg` |
| `website/public/assets/logo-white.svg` | `brand/inverse/icon-inverse.svg` |
| `website/public/assets/icon-64.png` | `brand/transparent/icon-64.png` |
| `opencastor-client/web/favicon.png` | `brand/transparent/icon-64.png` |
| `opencastor-client/web/icons/Icon-192.png` | `brand/transparent/icon-192.png` |
| `opencastor-client/web/icons/Icon-512.png` | `brand/transparent/icon-512.png` |
| `opencastor-client/web/icons/Icon-maskable-192.png` | `brand/transparent/android-chrome-192.png` |
| `opencastor-client/web/icons/Icon-maskable-512.png` | `brand/transparent/android-chrome-512.png` |
| `opencastor-client/web/icons/apple-touch-icon.png` | `brand/transparent/apple-touch-icon.png` |
| `opencastor-client/assets/images/logo.svg` | `brand/transparent/icon-transparent.svg` |
| `opencastor-client/assets/images/icon-128.png` | `brand/transparent/icon-128.png` |
| `opencastor-client/assets/images/icon-512.png` | `brand/transparent/icon-512.png` |

---

## Colors

| Name | Hex | Use |
|---|---|---|
| Midnight Blue Dark | `#0a0b1e` | Main dark background, dark mode surfaces |
| Midnight Blue Light | `#f8faff` | Main light background (soft indigo tint) |
| Accent Blue (Primary) | `#0ea5e9` | Primary actions, buttons, active states |
| Accent Teal (Secondary) | `#2dd4bf` | Secondary gradients, glow effects |
| Dark Navy | `#12142b` | Card backgrounds, inputs, borders (dark mode) |

## Usage Rules

- Maintain minimum clear space = height of the "O" in OpenCastor on all sides
- Do not recolor the robotic arm/castor geometry — use approved palette only
- **Transparent icon** for light/neutral backgrounds; **inverse icon** for dark backgrounds
- Do not stretch, skew, or distort — scale proportionally only
- Do not add effects (drop shadows, gradients, glows) to the logo mark itself
