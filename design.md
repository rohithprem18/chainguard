# ChainGuard UI Redesign — `design.md`

## 1. Product Direction

ChainGuard should feel like a **security intelligence product**, not a generic analytics dashboard.

The interface should communicate:

- Trust
- Technical credibility
- Fast risk interpretation
- Blockchain-native visual identity
- Strong model transparency
- Clear distinction between safe, suspicious, and high-risk addresses

The visual direction should be:

> **Dark security dashboard + Ethereum-native accents + restrained neon green + data-heavy but uncluttered.**

Avoid excessive gradients, glassmorphism, glowing borders everywhere, oversized cards, or decorative Web3 visuals that reduce readability.

---

# 2. Core Visual Style

## Theme

Use a dark theme as the primary experience.

### Base Colors

```css
--bg-primary: #05080D;
--bg-secondary: #090E16;
--surface-1: #0C131E;
--surface-2: #101925;
--surface-hover: #14202E;

--border-subtle: #1A2736;
--border-strong: #26384B;

--text-primary: #F5F7FA;
--text-secondary: #9AA9BA;
--text-muted: #6F8092;

--accent-primary: #39E58C;
--accent-primary-hover: #4FF09A;
--accent-soft: rgba(57, 229, 140, 0.12);

--blue: #4DA3FF;
--purple: #9B6BFF;
--yellow: #F7C948;
--red: #FF5D73;
```

### Risk Colors

```css
--risk-low: #39E58C;
--risk-medium: #F7C948;
--risk-high: #FF8A4C;
--risk-critical: #FF5D73;
```

Use risk colors only for actual risk semantics.

Do not use red, yellow, or green decoratively.

---

# 3. Typography

Use a clean modern sans-serif.

Recommended:

- `Inter`
- `Geist`
- `Manrope`

Optional monospace:

- `JetBrains Mono`
- `IBM Plex Mono`

Use monospace only for:

- Ethereum addresses
- Scores / model metrics
- hashes
- timestamps
- technical metadata

## Typography Scale

```txt
Hero heading       44px / 52px / 700
Section heading    24px / 32px / 650
Card heading       16px / 24px / 600
Body               15px / 24px / 400
Small              13px / 20px / 400
Metric             28px / 34px / 650
Risk score         64px / 68px / 700
```

Desktop hero text should not exceed ~720px width.

---

# 4. Global Layout

## Desktop

```txt
max-width: 1440px
content-width: 1240px
page horizontal padding: 40px
section gap: 28px
card gap: 20px
```

## Tablet

```txt
horizontal padding: 24px
```

## Mobile

```txt
horizontal padding: 16px
stack all major cards vertically
```

Do not stretch content edge-to-edge on large screens.

---

# 5. Header

## Structure

Left:

```txt
[Shield icon] ChainGuard
```

Right:

```txt
n=9,816 • PR-AUC 0.9451 • trained 2026-08-21
```

Optional secondary actions:

```txt
Model
Methodology
GitHub
```

Keep the header compact.

### Header Height

```txt
68–72px
```

### Logo

Use a simple shield outline with a small blockchain / node element inside.

Do not use a large illustrated logo.

---

# 6. Hero Section

Use a two-column layout.

## Left Column

Primary heading:

```txt
Score any Ethereum address
for patterns seen in
reported scam activity.
```

Highlight only:

```txt
reported scam activity.
```

with the primary green accent.

Supporting copy:

```txt
Paste an address to get a calibrated risk score and the
three behavioural patterns that contributed most.
```

## Right Column

Use a subtle Ethereum wireframe / abstract geometric visual.

Requirements:

- low opacity
- decorative only
- never compete with input
- no oversized floating 3D graphics

---

# 7. Address Search

This should be the main interaction on the page.

## Desktop Layout

```txt
[ Ethereum icon | 0x... address input                    ] [ Score address → ]
```

Input width should dominate.

Suggested sizing:

```txt
input height: 62px
button height: 62px
border radius: 12px
```

### Input States

Default:

```txt
border: subtle
```

Focus:

```txt
border: accent-primary
shadow: 0 0 0 3px rgba(57,229,140,.10)
```

Invalid:

```txt
red border
inline error
```

Loading:

```txt
button text → Analysing…
spinner
```

---

# 8. Recent Address Chips

Below the search input:

```txt
0x00020...4316
0x0000...05e8
0x0002...6fed
Clear
```

Selected chip:

```txt
green text
green subtle background
green border
```

Do not give every chip bright colors.

---

# 9. Main Risk Result Card

This should be the visual focus of the application.

Use a large card split into two sections.

```txt
┌─────────────────────────────────────────────────────────────┐
│ Risk Gauge          Address + status + summary              │
│                     Metrics                                 │
└─────────────────────────────────────────────────────────────┘
```

Suggested desktop ratio:

```txt
35% gauge
65% information
```

---

# 10. Risk Gauge

Use a circular gauge with a thin progress arc.

Center:

```txt
0.02
LOW RISK
Score
```

Avoid:

- thick donut charts
- aggressive glow
- too many labels

The score should be readable instantly.

## Risk Ranges

```txt
0.00 – 0.24     Low
0.25 – 0.49     Moderate
0.50 – 0.74     High
0.75 – 1.00     Critical
```

---

# 11. Address Summary

Display:

```txt
0x0000...05e8  [copy icon]

LOW RISK

This address's behaviour is consistent with normal,
low-risk historical activity.
```

Do not imply certainty.

Preferred wording:

```txt
Risk score
Behavioural indicators
Model estimate
Historical activity
```

Avoid:

```txt
This wallet is safe
This wallet is fraudulent
Guaranteed scam
```

---

# 12. Key Metrics

Display four metrics in one row:

```txt
↑ 721               ↓ 89
Sent                 Received

◎ 158               ◷ 489
Counterparties       Lifetime days
```

Each metric should contain:

- small icon
- strong numeric value
- short label

Use separators instead of separate mini-cards.

At the bottom:

```txt
Analysis based on 9,816 labelled addresses and 14 on-chain behavioural features.
```

---

# 13. Why This Score

This section explains model output.

Card title:

```txt
WHY THIS SCORE
```

Each explanation:

```txt
[icon] Receives from many distinct addresses          Strong
       This address receives funds from a very
       large number of unique addresses.

       ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

Recommended examples:

### Behaviour 1

```txt
Receives from many distinct addresses
Strength: Strong
```

### Behaviour 2

```txt
Long, sustained history of activity
Strength: Moderate
```

### Behaviour 3

```txt
Sends relatively few outgoing transactions
Strength: Weak
```

Do not label these as causes.

Use:

```txt
Contributing signal
Observed pattern
Behavioural indicator
```

---

# 14. Transaction Overview

Add a compact chart to make the product visually richer and more useful.

Suggested chart:

```txt
Sent vs Received transactions over time
```

Desktop:

```txt
Why This Score      Transaction Overview
50% width           50% width
```

Chart design:

- no chart border
- subtle horizontal grid
- two lines maximum
- minimal axis labels
- hover tooltip
- "All time" filter

Example:

```txt
Sent      green
Received  blue
```

---

# 15. Bottom Model Transparency Bar

Use one horizontal card.

```txt
[Shield] Model performance
         PR-AUC 0.9451

[Database] Trained on
           9,816 labelled addresses

[Target] Features
         14 on-chain signals

[Lock] Privacy first
       No raw data stored
```

This gives the project more credibility than a decorative footer.

---

# 16. Navigation / Optional Pages

If expanding ChainGuard beyond one page, use:

```txt
Dashboard
Methodology
Model
API
About
```

Recommended routes:

```txt
/
 /methodology
 /model
 /api
```

Do not add pages unless they contain real content.

---

# 17. Interaction Design

## Score Address

When clicked:

1. Validate Ethereum address.
2. Show loading skeleton inside result card.
3. Keep page layout stable.
4. Animate gauge from `0` to final score.
5. Fade in metrics.
6. Reveal top behavioural indicators.

Total transition:

```txt
400–700ms
```

Avoid long cinematic animations.

---

# 18. Loading State

Use skeletons instead of a blank screen.

```txt
Risk gauge skeleton
Address line skeleton
4 metric skeletons
3 explanation rows skeleton
```

Button:

```txt
Analysing…
```

---

# 19. Empty State

Before any address is scored:

```txt
No address analysed yet

Enter an Ethereum address to generate a calibrated
behavioural risk score.
```

Optional subtle shield illustration.

---

# 20. Error State

Example:

```txt
Unable to analyse this address.

Check that the address is a valid Ethereum address
and try again.
```

For API errors:

```txt
Analysis service unavailable.
Please retry in a moment.
```

Never expose raw backend stack traces.

---

# 21. Responsive Behaviour

## Desktop

```txt
Hero: 65 / 35 split
Risk result: 35 / 65 split
Analysis cards: 2 columns
Metrics: 4 columns
```

## Tablet

```txt
Hero visual reduced
Risk result remains 2 columns if space allows
Metrics: 2 × 2
```

## Mobile

```txt
Hero single column
Ethereum visual hidden
Search button full width
Risk gauge centered
Metrics: 2 × 2
Analysis cards stacked
Footer transparency items stacked
```

---

# 22. Card Styling

Use consistent cards.

```css
background: #0C131E;
border: 1px solid #1A2736;
border-radius: 16px;
box-shadow: 0 8px 30px rgba(0,0,0,.16);
```

Highlighted risk card may use:

```css
border-color: rgba(57,229,140,.42);
```

Avoid giving every component neon borders.

---

# 23. Icons

Recommended icon libraries:

```txt
Lucide React
Phosphor Icons
```

Suggested icons:

```txt
ShieldCheck
Search
ArrowRight
Copy
ArrowUp
ArrowDown
Users
Clock3
Info
Database
Lock
Activity
ExternalLink
```

Use one icon family consistently.

---

# 24. Accessibility

Required:

- WCAG AA contrast
- visible keyboard focus
- input labels for screen readers
- `aria-live` for score result
- do not rely only on color for risk
- chart must have text summary
- minimum touch target: 44px

Risk labels must always include text:

```txt
LOW RISK
MODERATE RISK
HIGH RISK
CRITICAL RISK
```

---

# 25. Motion

Keep motion subtle.

Recommended:

```txt
button hover       120ms
card hover         160ms
result reveal      300ms
gauge animation    600ms
chart fade         350ms
```

Use:

```css
cubic-bezier(0.22, 1, 0.36, 1)
```

Avoid continuous glowing, spinning, floating, or pulsing elements.

---

# 26. Recommended Component Structure

```txt
src/
├── components/
│   ├── Header.tsx
│   ├── AddressSearch.tsx
│   ├── RecentAddresses.tsx
│   ├── RiskScoreCard.tsx
│   ├── RiskGauge.tsx
│   ├── WalletMetrics.tsx
│   ├── RiskExplanation.tsx
│   ├── TransactionChart.tsx
│   ├── ModelStatsBar.tsx
│   ├── LoadingState.tsx
│   └── ErrorState.tsx
│
├── pages/
│   ├── Dashboard.tsx
│   ├── Methodology.tsx
│   └── Model.tsx
│
└── styles/
    └── tokens.css
```

---

# 27. Suggested Dashboard Hierarchy

```txt
HEADER

HERO
├── Headline
├── Explanation
└── Ethereum visual

ADDRESS SEARCH
├── Input
├── Score button
└── Recent addresses

RISK RESULT
├── Gauge
├── Address
├── Risk level
├── Interpretation
└── Key metrics

ANALYSIS
├── Why this score
└── Transaction overview

MODEL TRANSPARENCY
├── PR-AUC
├── Dataset size
├── Features
└── Privacy
```

---

# 28. Changes From Current UI

## Keep

- Address-first interaction
- Large score visualization
- Recent address chips
- Behavioural explanation
- Model performance metadata
- Clean dashboard structure

## Improve

### Current

```txt
Large unused white space
Single flat card
Limited visual hierarchy
Generic button styling
Weak blockchain identity
Metrics feel disconnected
Explanations look like progress bars without context
```

### Redesigned

```txt
Dark security-focused interface
Clear hierarchy
Integrated risk summary
Compact metric system
Transaction visualization
Model transparency strip
Subtle Ethereum identity
Better loading / empty / error states
Responsive layout
```

---

# 29. Implementation Priority

## Phase 1 — Visual Foundation

```txt
Dark theme
Color tokens
Typography
Header
Search component
Card system
Responsive container
```

## Phase 2 — Result Experience

```txt
Risk gauge
Risk state colors
Metrics
Address copy interaction
Behaviour explanations
```

## Phase 3 — Data Visualization

```txt
Transaction chart
Tooltips
Time filter
Loading skeleton
```

## Phase 4 — Polish

```txt
Animations
Accessibility
Empty state
Errors
Mobile refinement
```

---

# 30. Final Design Principle

ChainGuard should look like:

> **A production-grade blockchain security product backed by machine learning.**

It should not look like:

> **A generic AI-generated Web3 landing page.**

Every visual element should help the user answer one question quickly:

> **How risky is this address, and why did the model score it this way?**
