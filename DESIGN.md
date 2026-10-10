---
name: Limits
description: Minimal iPhone subscription usage utility
colors:
  paper: "#f5f4ee"
  ink: "#193530"
  muted: "#566761"
  line: "#d8dcd2"
  track: "#e2e5dc"
  claude: "#a44b2d"
  codex: "#217563"
  warning: "#855118"
  paper-dark: "#14231f"
  ink-dark: "#f0f1e8"
  muted-dark: "#afbeb6"
  line-dark: "#3b4c43"
  track-dark: "#34463e"
  claude-dark: "#f5a583"
  codex-dark: "#80cdb6"
  warning-dark: "#ebbc7b"
typography:
  display:
    fontFamily: '-apple-system,BlinkMacSystemFont,"Helvetica Neue",sans-serif'
    fontSize: "44px"
    fontWeight: 750
    lineHeight: 1.15
    letterSpacing: "-.035em"
  title:
    fontSize: "23px"
    fontWeight: 650
    letterSpacing: "-.025em"
  body:
    fontSize: "17px"
  window-label:
    fontSize: "15px"
    fontWeight: 550
  button:
    fontSize: "14px"
    fontWeight: 600
  issue:
    fontSize: "13px"
    lineHeight: 1.5
  label:
    fontSize: "12px"
    fontWeight: 600
  countdown:
    fontSize: "12px"
    lineHeight: 1.5
rounded:
  button: "12px"
  meter: "3px"
spacing:
  heading-gap: "12px"
  header-gap: "16px"
  gutter: "24px"
  compact-gutter: "18px"
  window-gap: "24px"
components:
  refresh-button:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    typography: "{typography.button}"
    rounded: "{rounded.button}"
    padding: "10px 12px"
  refresh-button-hover:
    backgroundColor: "{colors.track}"
  provider:
    padding: "25px 0 30px"
  quota-meter:
    backgroundColor: "{colors.track}"
    rounded: "{rounded.meter}"
    height: "7px"
    width: "100%"
---

# Design System: Limits

## Overview

**Creative North Star: "Operate"**

Minimal iPhone utility with native UI typography, a paper surface, and clear
measurements. Remaining percentage, reset countdown, and provider freshness remain
visible together. Dark appearance follows the system preference.

**Key Characteristics:**
- Two flat provider sections separated by rules.
- Clay Claude and green Codex accents.
- Explicit unavailable, stale, and offline readings.

## Colors

### Primary
Clay identifies Claude usage and current status.

### Secondary
Green identifies Codex usage, the title dot, and keyboard focus.

### Neutral
Paper and ink carry the page; muted text carries supporting information.
Line separates sections, track carries meter backgrounds, and warning marks
connection or provider problems. Each role has a system-dark counterpart.

## Typography

The native font stack applies throughout. Display names the utility; title
sizes provider names and quota values. Body introduces the page; window labels
name periods. Button, issue, label, and countdown roles keep utility text compact.
Quota values and countdowns use tabular numerals.

## Layout

A single column has a maximum width (560px), centered with the gutter token.
Top padding adds the safe-area inset to (32px); bottom adds its inset to (24px).
Header and row pairs align labels with actions or measurements. Below (350px),
the compact gutter applies and the refresh label hides while its icon remains.

## Elevation & Depth

No shadows. Rules, whitespace, and meter tracks establish separation.

## Shapes

Provider sections are flat and ruled. Refresh uses the button radius; meters
use the meter radius and clip their fill. There are no card surfaces.

## Components

Refresh has a transparent surface and line border. Hover uses track; keyboard
focus uses a green outline (3px), offset (4px). Disabled opacity is (0.6).
Its minimum width and height are (44px).

Provider headings pair names with textual Current, Stale, or Unavailable status.
Each period pairs a remaining percentage with a thin meter and reset countdown.
Unavailable measurements show a dash and explanation, with their meter hidden.
Last-success text remains below each provider. Connection status precedes both.

## Do's and Don'ts

### Do:
- Do keep quota values, reset countdowns, and freshness visible together.
- Do preserve safe-area spacing and minimum 44px touch targets.
- Do identify stale, unavailable, and offline readings in text.

### Don't:
- Don't infer quota values when data is unavailable.
- Don't depend on color alone to communicate freshness.
