# Industrial Design Specification: Tactical Dark Mode

## Goal
Transform the AOI Review Workstation from a "friendly" web application into a **high-precision industrial hardware interface**. The design prioritizes high-contrast data visibility, reduced eye strain for long shifts, and an aesthetic of engineering precision.

---

## 1. Core Palette (Tactical Dark)

Industrial interfaces use deep, cool grays to reduce glare and make the board scan colors (Green/Blue/Gold) stand out.

| Layer | Color Hex | Use Case |
| :--- | :--- | :--- |
| **App Background** | `#0D1117` | Main container background |
| **Surface (Level 1)** | `#161B22` | Main panels (Run History, Review Sidebar) |
| **Surface (Level 2)** | `#21262D` | Cards, buttons, and hovered items |
| **Borders/Dividers** | `#30363D` | Thin 1px lines to define sections (No shadows) |
| **Text Primary** | `#C9D1D9` | General UI labels and descriptions |
| **Text Secondary** | `#8B949E` | Dimmed metadata and eyebrow labels |
| **Accent Blue** | `#58A6FF` | Focus states, active toggles, and "Precision" elements |

---

## 2. Status Colors (Action Palette)

Status indicators must be unmistakable and high-contrast. 

*   **FAIL (Critical):** `#F85149` (Vivid Red)
*   **PASS (Nominal):** `#3FB950` (Electronic Green)
*   **CAUTION (Warning):** `#DBAB09` (Safety Yellow)
*   **INFO (Action):** `#58A6FF` (Precision Blue)

---

## 3. Precision Geometry & Density

Industrial tools focus on "Information Density" and "Solid Construction."

*   **Corner Radius:** **4px** (Sharp/Machined)
*   **Borders:** **1px Solid** for all panel definitions. 
*   **Shadows:** **None.** 
*   **Layout Priority:** Density leads. Tightened padding (20-30%) and smaller components to maximize visible board and data rows.

---

## 4. Technical Typography

Precision measurement requires precision alignment.

*   **UI Labels:** `Inter` or `System Sans-Serif`.
*   **Data Fields (Priority):** `Monospace` (JetBrains Mono, Roboto Mono, or SF Mono).
    *   *Required for: PCB IDs, Coordinates (X, Y), Confidence Scores, and Timestamps.*
    *   *Reasoning: Vertical alignment of digits and fixed-width identifiers.*

---

## 5. Component Specifics

### Floating HUD (Heads-Up Display)
The Inspector will be treated as a "Glass Terminal" overlay.
*   **Background:** `#161B22` with `0.9` opacity and `12px` Backdrop Blur.

### PCB Viewer Stage
*   **Canvas Background:** Pure Black (`#000000`).
*   **Coordinate Grid:** Subtle translucent gray grid (10px x 10px). **Visible only when zoomed in (> 1.5x)** to avoid noise.

---

## 6. UI Symbols
*   **No Literal Emojis:** Use clean, geometric **inline SVGs** for all UI actions.
*   **Symbols:**
    *   **List Icon** -> Run History Toggle
    *   **Search/Adjust Icon** -> Filters Toggle
    *   **Sidebar Icon** -> Defect List Toggle

---

## 7. Ergonomics
*   **Interactive Targets:** Buttons must be at least `32px` high for fast mouse interaction.
*   **Hover States:** High-contrast background shift (Slate to Light Slate) to confirm selection intent.
*   **Focus Ring:** `2px` offset Blue ring for keyboard/tab navigation.
