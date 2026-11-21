# Design: "Placement desk"

One direction: Ping is a **focused inbox for placement season**, not a messenger. The thread reads like a desk
where a careful assistant drops sorted notes: what closes tonight, what names you, what's new. Calm paper
neutrals, ink text, one teal accent for "this is for you", and a few semantic colours that always mean the same
thing. No gradients, no avatars per message, no decoration that doesn't carry information.

Stack: static HTML, one CSS file, vanilla JavaScript. System font stack (no download): fast on campus Wi-Fi.

## Palette

Tokens live on `:root` in `dashboard/style.css`; dark values follow the system and a toggle (Profile > Account).
Every text colour below meets 4.5:1 on the surface it sits on (checked by `tests/test_design_contrast.py`).

| token | light | dark | used for |
|---|---|---|---|
| `--bg` | `#f4f2ec` paper | `#121513` | page background |
| `--surface` | `#ffffff` | `#1b1f1c` | cards, bubbles, sheets |
| `--thread` | `#ecebe4` | `#0e110f` | the thread behind bubbles |
| `--ink` | `#1b1c19` | `#eceeea` | body text |
| `--muted` | `#5a5b53` | `#a3a99f` | secondary text, reasons, times |
| `--line` | `#dddbd2` | `#2d332f` | borders, dividers |
| `--accent` | `#0e6b5c` teal | `#5cc9ae` | the one accent: For you, primary actions, focus |
| `--accent-soft` | `#e0f1ec` | `#163029` | your own messages, selected chips |
| `--applied` | `#33527a` slate | `#9db8e0` | "✓ applied" |
| `--soon` | `#8a4b00` amber | `#f0b46a` | closing soon, reminders, countdowns |
| `--test` | `#5b3fb0` violet | `#c3b0f5` | tests, interviews, room lists |
| `--danger` | `#a8322a` | `#ff8f86` | errors, "not on the list" |

Each semantic colour has a `-soft` background for chips and card edges.

## Type

System stack: `system-ui, -apple-system, "Segoe UI", Roboto, "Noto Sans", sans-serif`.

| step | size / line | use |
|---|---|---|
| `--t-xs` | 12 / 16 | times, source lines, badges |
| `--t-sm` | 14 / 20 | secondary text, rows in lists |
| `--t-md` | 16 / 24 | body, bubbles, inputs (16 px also stops iOS zooming into inputs) |
| `--t-lg` | 18 / 26 | card titles, digest headings |
| `--t-xl` | 24 / 30 | page titles |

Weights: 400 body, 600 headings and labels. Numbers that change (countdowns) use tabular figures.

## Spacing, radius, elevation

- Spacing scale: 4, 8, 12, 16, 24, 32 (`--s1` ... `--s6`).
- Radius: 8 controls, 14 cards and bubbles, 999 chips and pills.
- Elevation: one shadow (`--shadow`) for sheets and the unread pill; cards are flat with a 1 px line.
- Tap targets: 44 px minimum for anything you can press.

## Message kinds (bubble anatomy)

All of Ping's messages sit on the left at up to 640 px; yours on the right. Each has a **kicker** (a small label on
top: what kind of message), the **title**, the **body** and a **footer** (source line, time).

| kind | edge / kicker | body |
|---|---|---|
| **Digest** (applications closing together) | amber edge; kicker "Closing tonight 20:00" + a countdown chip ("in 1h 56m" / "over") | "For you" rows (company — role, reason in muted text, "Apply with: CV", ✓ applied badge), then "Others (N)" collapsed; eligibility note; source line |
| **Reminder** | amber edge, kicker "Reminder" + countdown chip | same rows, unapplied only |
| **Test alert** (test, room list, interview) | violet edge, kicker "Test" + time chip ("in 2 h" / "over") | where, your row (slot, room), link |
| **New roles** | neutral edge, kicker "New roles" | rows grouped by close time |
| **You applied / about you** | teal edge, kicker "You applied" | the update (extension, shortlist, result) |
| **Ping system note** | no bubble: centred muted line | "Couldn't reach the ERP for the last 3 runs; I'll keep trying." |
| **Your message** | right side, `--accent-soft` fill | your text |
| **Ping's answer** | left, plain surface | the answer; lists keep the same row format |

Past items fade to 70% with a "Passed" kicker. New messages fade and rise in over 150 ms (nothing moves for
people who ask for reduced motion), and nothing above them shifts.

## Chat furniture

- **Day headers** stick to the top of the thread while you scroll through that day.
- **Unread pill**: "N new" floats above the composer; tapping it scrolls to the unread divider.
- **Typing indicator**: three dots in a small bubble while Ask Ping answers.
- **Quick replies**: a row of chips above the box ("What's due tonight?", "Anything for me?", "Which CV for ...?").
- **Send button**: disabled while empty; shows "…" while waiting.
- **Composer** stays above the on-screen keyboard (dynamic viewport and `interactive-widget=resizes-content`).

## Navigation

- Phone (< 900 px): a bottom bar with Chat · Companies · Profile (icons with labels, 56 px tall, safe-area aware).
- Desktop (≥ 900 px): a slim left rail with the same three, plus Check now and the theme toggle.
- No hamburger menu.

## Pages

- **Companies**: a search box, filter chips [For you] [Applied] [Closing soon] [All], one row per role. The company
  is the primary line (bold, body size) with the CTC right-aligned on it; the role sits below, one step smaller and
  regular weight; then close time with countdown, badges and "Apply with". The role sheet's header keeps the same
  order (company, then role). Company names are cleaned for display only (`dashboard/names.js`): a website in
  brackets ("Auro Group(www.AuroIM.com)") and double spaces go; the raw ERP name stays in the data. Tapping a row opens a **role sheet** (a bottom
  sheet on phones, a side panel on desktop) with everything Ping knows: CTC breakdown, eligibility and why,
  deadlines and where they came from, the company's notices, your results on its lists, the source.
- **Profile**: cards (About you · What I'm looking for · CVs · Schedule & reminders · Account), each edited in place
  with its own Save; the same fields the onboarding and the chat set.

## Empty states

One sentence that says what will appear and when, plus at most one action. Examples: "No messages yet. Ping posts
here after its first check (about 10 minutes)." / "No roles match. Try All."

## Accessibility

Text contrast ≥ 4.5:1 in both themes; visible 2 px focus rings in `--accent`; 44 px tap targets; a label on every
control (visible or `aria-label`); `prefers-reduced-motion` turns off every animation; the thread is a `log`
region so screen readers hear new messages.
