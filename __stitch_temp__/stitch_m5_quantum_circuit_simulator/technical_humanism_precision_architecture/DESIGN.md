---
name: Technical Humanism & Precision Architecture
colors:
  surface: '#fbf9f6'
  surface-dim: '#dbdad7'
  surface-bright: '#fbf9f6'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f5f3f0'
  surface-container: '#efeeeb'
  surface-container-high: '#eae8e5'
  surface-container-highest: '#e4e2df'
  on-surface: '#1b1c1a'
  on-surface-variant: '#474741'
  inverse-surface: '#30312f'
  inverse-on-surface: '#f2f0ed'
  outline: '#777771'
  outline-variant: '#c8c7bf'
  surface-tint: '#5f5e5c'
  primary: '#000000'
  on-primary: '#ffffff'
  primary-container: '#1c1c1a'
  on-primary-container: '#858481'
  inverse-primary: '#c9c6c3'
  secondary: '#9b432c'
  on-secondary: '#ffffff'
  secondary-container: '#fe9073'
  on-secondary-container: '#752813'
  tertiary: '#000000'
  on-tertiary: '#ffffff'
  tertiary-container: '#1e1b15'
  on-tertiary-container: '#89837a'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#e5e2de'
  primary-fixed-dim: '#c9c6c3'
  on-primary-fixed: '#1c1c1a'
  on-primary-fixed-variant: '#474744'
  secondary-fixed: '#ffdbd2'
  secondary-fixed-dim: '#ffb4a1'
  on-secondary-fixed: '#3c0800'
  on-secondary-fixed-variant: '#7c2d17'
  tertiary-fixed: '#e9e1d6'
  tertiary-fixed-dim: '#ccc6bb'
  on-tertiary-fixed: '#1e1b15'
  on-tertiary-fixed-variant: '#4a463e'
  background: '#fbf9f6'
  on-background: '#1b1c1a'
  surface-variant: '#e4e2df'
typography:
  display-hero:
    fontFamily: Newsreader
    fontSize: 48px
    fontWeight: '400'
    lineHeight: 56px
    letterSpacing: -0.015em
  display-hero-mobile:
    fontFamily: Newsreader
    fontSize: 32px
    fontWeight: '400'
    lineHeight: 40px
    letterSpacing: -0.01em
  headline-lg:
    fontFamily: Newsreader
    fontSize: 36px
    fontWeight: '400'
    lineHeight: 44px
    letterSpacing: -0.01em
  headline-lg-mobile:
    fontFamily: Newsreader
    fontSize: 26px
    fontWeight: '400'
    lineHeight: 34px
  headline-md:
    fontFamily: Newsreader
    fontSize: 24px
    fontWeight: '400'
    lineHeight: 32px
  headline-sm:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '500'
    lineHeight: 26px
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 28px
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 22px
  body-sm:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 20px
  meta-label:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.08em
  data-metric:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 18px
spacing:
  gutter: 1.5rem
  margin: 2.5rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 1rem
  space-lg: 1.75rem
  space-xl: 3rem
---

## Brand & Style
This design system pairs the rigorous discipline of scientific instrumentation and architectural blueprints with the tactile warmth of archival editorial printing. It rejects the saturated gradients, heavy card containers, and synthetic drop shadows common in modern SaaS interfaces. Instead, it anchors its visual voice in quiet authority, intellectual precision, and intentional restraint.

### Aesthetic Principles
- **Archival Precision:** Interfaces feel like fine lithographs or scientific journals printed on heavy cotton rag paper. Space is generous, measured, and calculated.
- **Hairline Orthography:** Structure is expressed through ultra-fine 1px hair lines, isometric wireframe drawings, delicate coordinate ticks, and ruled dividing axes rather than elevated surface cards.
- **Typographic Hierarchy:** Authoritative editorial serif headlines set against monospaced scientific telemetry and balanced sans-serif body copy create a clear, multi-layered reading cadence.
- **Deliberate Restraint:** Color is applied sparingly. The vast majority of the interface lives in tonal values of warm ivory, bone, charcoal, and obsidian, reserving terracotta/umber purely for focal emphasis and critical state changes.

## Colors
The palette is built around an archival warm paper substrate, deep mineral carbon inks, and an earthy umber accent.

### Color Tokens & Roles
- **Canvas Base (`#FAF8F5`):** The primary paper substrate. Calibrated to reduce eye fatigue while providing a tactile, editorial foundation.
- **Subsurface Ivory (`#F4EFEA`):** Used for subtle panel contrasts, table header fills, and recessed interactive surfaces.
- **Rule & Hairline Lineage (`#E2DDD5` / `#CCC6BB`):** 1px structural gridlines, timeline axes, and coordinate ticks.
- **Obsidian / Carbon (`#1A1A18`):** Primary ink for headlines, major architectural diagrams, and active milestone states.
- **Stone Charcoal (`#4A4641`):** Body typography, secondary metrics, and unselected milestone labels.
- **Muted Silt (`#8C877D`):** Inactive timeline nodes, tick marks, and tertiary scientific metadata tags.
- **Terracotta / Burnt Umber (`#A44A32`):** Deliberate focal point accent used for active milestone indicators, delta highlights, and critical scientific thresholds.

## Typography
Typography creates tension between humanistic editorial prose and machine telemetry.

### Typographic Rules
- **Display & Headlines:** Set in **Newsreader**. Headlines should maintain natural optical sizing with restrained weights (Regular 400). Avoid bold weights on serif displays to keep the stroke contrast crisp and calligraphic.
- **Body Text:** Set in **Inter** for neutral, utilitarian readability against complex technical diagrams.
- **Metadata & Milestone Ticks:** Set strictly in **JetBrains Mono** with uppercase casing and wide letter tracking (`letterSpacing: 0.08em` to `0.12em`). Mathematical superscripts (e.g., `10^2`, `10^-6`) must use proper unicode glyphs or superscript tags with monospaced alignment.

## Layout & Spacing
The layout follows an architectural grid structure inspired by drafting paper and engineering folios.

### Grid & Structure
- **Desktop (1200px+):** 12-column or continuous horizontal modular timeline track with `2.5rem` outer canvas padding and `1.5rem` gutters.
- **Tablet (768px - 1199px):** 6-column fluid grid, horizontal timeline converted into a drag-scrollable linear track with visual edge fades.
- **Mobile (< 768px):** Reflows into a single-column vertical drafting axis where the timeline runs down the left margin with nodes protruding to the right.
- **Vertical Spacing Cadence:** Large architectural zones require generous separation (`3rem` to `6rem`) to let technical wireframes breathe without visual crowding.

## Elevation & Depth
This design system avoids drop shadows, blur effects, and layered elevated cards. Depth is purely planar and graphic:

- **Hairline Stratification:** Boundaries between sections, headers, and timeline bands are defined by single `1px solid #E2DDD5` rules.
- **Architectural Line Art:** Depth is conveyed exclusively inside the isometric and orthographic wireframe graphics through line density, stippling, and cross-hatching rather than canvas elevations.
- **Surface Insets:** Interactive regions (such as code inspection panels or telemetry drawers) rely on flat background color shifts from Canvas (`#FAF8F5`) to Subsurface (`#F4EFEA`) with a crisp `1px` stroke.

## Shapes
Shapes in this design system are strictly architectural and sharp (`0px` border radius). 

Buttons, table cells, metric badges, and timeline indicators feature clean 90-degree corners. The only circular forms permitted are functional coordinate nodes along the timeline axis, diagram geometry, and radial radio inputs. This structural sharpness reinforces the physical feeling of technical drawings, parchment prints, and precision hardware schematics.

## Components

### Timeline Track & Milestone Nodes
- **Axis Line:** A continuous `1px` horizontal line (`#CCC6BB`) spanning across all milestones.
- **Milestone Nodes:** A `9px` circular node centered on the axis. Default state is an empty ring with a `1.5px` border in `#8C877D`; current or completed state is filled solid in `#1A1A18` or accented in `#A44A32`.
- **Tick Marks:** `6px` vertical hairpins intersecting the timeline indicating intermediate steps or calendar intervals.
- **Milestone Header:** Monospace uppercase tracking above milestone titles (`MILESTONE 01`), followed by the descriptive title in medium weight, followed by stacked metadata lines in mono (`Physical Qubits: 10²`).

### Buttons
- **Primary:** Solid carbon background (`#1A1A18`), warm paper text (`#FAF8F5`), 0px border radius, `12px 24px` padding, font set in Inter Medium `14px`. Hover initiates an instant tint transition to `#33322E`.
- **Secondary / Outline:** Transparent background, `1px solid #1A1A18`, charcoal text (`#1A1A18`). On hover, fills with `#F4EFEA`.
- **Technical Action:** JetBrains Mono uppercase `11px`, framed with `1px solid #CCC6BB`, featuring a trailing bracket `[ → ]`.

### Technical Cards & Panels
- Replaces traditional rounded SaaS cards with framed drafting folios.
- Background: `#FAF8F5` or `#F4EFEA`.
- Border: `1px solid #E2DDD5`.
- Corners: Optional hairline corner crosshairs (`+`) extending 4px beyond the border perimeter for scientific drafting emphasis.

### Metric Callouts & Data Tags
- **Tag Container:** Minimalist borderless tag or single hairline boundary with `4px 8px` padding.
- **Content:** Label in `8C877D` (JetBrains Mono 11px uppercase) paired with value in `#1A1A18` (JetBrains Mono 12px Regular).

### Inputs & Form Fields
- Underline-only or 4-sided hairline boxes (`1px solid #CCC6BB`).
- Background: `#FAF8F5` (blends seamlessly into canvas).
- Focus State: Border transitions to `#1A1A18` with no glow or shadow. Placeholder rendered in `#8C877D`.