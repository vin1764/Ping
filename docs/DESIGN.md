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

## Chat (a familiar messaging app)

**Header, like a contact.** A round avatar with Ping's mark, the name, and a status line that is Ping's state, from
the runs table in real time: "checked 4 min ago" (ticks; "last checked 13:24" after an hour) → "checking the ERP…"
(the dots move, a ring pulses around the avatar) → "found 2 new" (2 s, the avatar flashes amber) → back.

**Bubbles with tails.** Ping's on the left (`--bubble-ping`: white in light, dark grey in dark), yours on the right
tinted green (`--bubble-me`). The tail is on the first bubble of a run; following bubbles from the same side sit
closer and have none. The time sits inside the bubble, bottom right. Date pills ("Today", "Yesterday", "Thu 19 Nov")
stick to the top while you scroll that day. Behind the thread is our own wallpaper: small line drawings (Ping's mark,
a clock, a calendar page, an envelope, a briefcase, a tick, a notice, a sparkle) at 6-10% opacity, tinted to the
theme. It was drawn for Ping, not copied from any app.

**The label line.** Every message from Ping starts with a small coloured label: **REMINDER** (amber: applications
or forms closing), **TEST** (violet: tests, room lists, shortlists, results), **NEW** (green: new roles), **PING**
(slate: Check now and hourly checks), plus QUESTION (when Ping needs you) and UPDATE (about a role you applied to).
Then the title and body. A digest lists "For you" rows (company — role, the reason, "Apply with: CV", ✓ applied)
and ends with **"Show 30 more ▸"**, which opens the other roles in place.

**Countdown chips** tick every second on the page's clock: "in 1 h 48 m", "in 42 m", "in 35 s", "over". Neutral
over 3 h, **amber under 3 h**, **red under 1 h** (with a slow beat), outlined grey when over. One format everywhere
(`dashboard/today.js countdown`): chat, Today, Companies.

**Motion** (all off for people who ask for reduced motion): a new bubble rises 10 px and fades in over 160 ms; the
typing bubble's three dots bounce while Ask Ping answers (at least 0.6 s, so it never flickers); the send button is an
outlined circle when empty, filled when there's text, and presses in; quick-reply chips press in; the "N new ↓" pill
slides up; loading shows skeleton bubbles, not words; a message opened from Today flashes its outline.

Past items fade to 70% with their own label ("Deadline passed", "Over").

## Today

Desktop (≥ 1100 px): a right rail beside the chat. Phones: a fourth tab (Chat · Today · Companies · Profile) whose
badge counts what's still ahead today. In time order:

- every **test** today: company, role, time, room or slot when a list gave them, "you're on the list" / "not on the
  list", and the countdown;
- every **deadline** today: the time, "N for you · M applied", the for-you companies; forms and submissions due;
- **notices** that arrived today, one line each (a notice for several companies leads with its subject);
- the **next ERP check** (a plain time, not a deadline's colours).

What's over moves to the bottom, struck through. A tap opens the chat message it came from (which flashes), else the
role sheet, the notice or the company. Under the list: "Tomorrow: 2 tests, 4 deadlines" (or "nothing scheduled
yet"). An empty day says "Nothing scheduled today. Next check 14:11." The demo gets the same panel from its snapshot,
on a clock that starts at the snapshot time and moves on; its first Check now finds what the snapshot's last check
brought, later ones find nothing new.

## Chat furniture

- **Unread pill**: "N new ↓" slides in above the composer; tapping it scrolls to the first one.
- **Quick replies**: a row of chips above the box ("What's due tonight?", "Anything for me?", "Which CV for ...?").
- **Composer** stays above the on-screen keyboard (dynamic viewport and `interactive-widget=resizes-content`); the
  bottom bar steps aside while you type.

## Navigation

- Phone (< 900 px): a bottom bar with Chat · Today · Companies · Profile (icons with labels, 56 px tall, safe-area
  aware); Check now is a round icon in the header.
- Desktop (≥ 900 px): a slim left rail with the same, plus Check now and the theme toggle; from 1100 px Today sits
  beside the chat instead of being a tab.
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


## Tone (every message, label, empty state and error)

- Short and specific: say what happened and what to do, in one or two sentences. "Nothing due tomorrow (Mon 23 Nov)."
  not "There are no deadlines in the data for the requested date."
- Never "the data does not contain", "I don't have any information" or "as an AI": say what is missing and where it
  would come from ("No Esri notice yet.", "The ERP doesn't publish test scores.").
- Times in IST, 24-hour, always with the day when it isn't today: "20:00", "Sun 22 Nov 17:00". No "PM", no seconds.
- Company first, then the role: "Groww (Product Analyst)", "Axon Developers: fill the form by 17:00".
- Sentence case everywhere ("Check now", "Show 30 more", "Install Ping"); no title case, no shouting.
- No jargon: no function, server, Supabase, token, RLS, realtime, JSON in anything a student reads. Owner-only setup
  messages may name a setting, and then say exactly where it is.
- Errors say what still works: "Ping's assistant couldn't be reached, so this answer comes straight from the ERP data."
