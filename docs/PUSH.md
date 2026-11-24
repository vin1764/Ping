# Ping as an app, with notifications

Ping installs from the browser like an app (Android, iPhone, desktop Chrome/Edge) and can notify your phone when
something is for you. Nothing changes for anyone who doesn't install it: the same page works in any browser.

## What you get

- **An app icon** that opens straight to the chat, full screen, and opens instantly (the app is kept on the phone).
- **Offline reading:** without a connection Ping opens with the thread as it was last loaded, and says so. What you
  send offline waits ("waiting for a connection") and is asked in order when you're back online.
- **Notifications** (only if you say yes, per device):
  - at most **one per check**, for the most urgent new thing **you** have to do. The title says who and what to do,
    the body only what you need to act (the role, "Apply with <CV>", the countdown), in one or two short lines:

    | what | title | body |
    |---|---|---|
    | an application | `ZS Associates · Apply by tomorrow 20:00` | `Decision Analytics Associate · Apply with PM CV · in 23 h` |
    | a form | `Piramal Finance · Fill form by 20:00` | `in 3 h 10 min` |
    | a deadline moved (only if you haven't applied / filled; otherwise nothing) | `Meesho · Deadline extended to Wed 14:00` | the role, the countdown |
    | a test you're on | `Groww · Test at 15:00 · Room 304` | the role, the countdown |
    | a shortlist with your name | `FirstClub · You're on the shortlist` | the role |
    | a new role for you | `Bluestone · New role for you: APM` | `apply by 22:00 · in 1 h` |
    | several due at the same time | `2 to apply by tomorrow 20:00` | one per line, `Company — Role`; more than 3: the first 3 and "and 2 more" |

    Roles that aren't for you ("Others") are never in a notification. "Nothing new" checks send nothing.
    Tapping it opens the matching Today sheet (the forms or the roles due then), or the test / shortlist message;
  - **test-day reminders**: for a test a list says you're on, at your reminder lead time ("Groww · Test at 15:00 ·
    Room 304"), sent by Supabase's scheduler even if no check runs then;
  - **mail-only deadlines**: a form or a "complete the test by" that only your placement mail has (no ERP notice
    says it) gets the same reminder at your lead time ("Pine Labs · Fill form by 17:00");
  - **never in your quiet hours**: outside your check window (Profile > Schedule, default 06:00 to 01:00 IST);
  - tapping one opens the chat **at that message** (it flashes).
- **Optional email** of the same for-you messages (Profile > Notifications > "Also email me", off by default). The
  email after 3 failed checks is sent as before, whatever this says.

## Turning it on (owner)

1. Actions > Admin > `apply-sql` (the tables), then `push-setup` (the keys: one click; it also redeploys the
   dashboard with the public key), then `schedule-setup` (adds the 5-minute reminder job). Or from a terminal:
   ```
   gh workflow run admin.yml -f task=push-setup
   ```
   Without GitHub: `python -m ping.push keys` prints a key pair; put `VAPID_PRIVATE_KEY`, `VAPID_PUBLIC_KEY` and
   `VAPID_SUBJECT` (your dashboard's address) in the Supabase function secrets and the public key in
   `dashboard/push-public-key.txt`.
2. On the phone, follow **Check it on your phone** below.

## How it works

| piece | where |
|---|---|
| manifest, icons, offline app shell | `dashboard/manifest.webmanifest`, `dashboard/icons/`, `dashboard/sw.js` (build.sh writes the build id into it) |
| the last thread for offline, the send queue | IndexedDB `ping` on the phone (`dashboard/app.js`: `kv`, `OfflineSource`, `queueSend`) |
| a device saying yes | `push_subscriptions` (endpoint + the browser's public keys; owner-only row rules, a demo session can't subscribe) |
| which message, its label and first line | `ping/push.py` (run at the end of every check; tests in `tests/test_push.py`) |
| sending (VAPID, encryption) | the `send-push` Supabase function; the VAPID private key is a Supabase function secret only |
| test-day reminders | `push_queue` rows written by the check; pg_cron job `ping-push-due` calls `send-push` every 5 minutes |

**The notification Ping sends** (the JSON inside the encrypted Web Push message; the phone shows title and body):

```json
{
  "title": "2 to apply by tonight 20:00",
  "body": "Navi — SDE-1 · Apply with Tech CV\nMoneyview — Data Scientist\nin 3 h",
  "url": "./#sheet/apply/1795530600000",
  "tag": "sample:digest:application:20261121T2000"
}
```

A test-day reminder: `{"title": "Groww · Test at 15:00 · Room 304", "body": "APM", "url": "./#m-…"}`.
The request to the push service carries `Content-Encoding: aes128gcm` (RFC 8291), `TTL: 21600` (6 h),
`Urgency: high` and `Authorization: vapid t=<JWT signed with the private key>, k=<public key>`.

## How it was checked without a phone

- `node setup/pwa_check.js` (headless Chromium, on the live site): the manifest is linked and valid (name, short
  name, standalone, theme colour, start URL and scope under `/ping-dashboard/`), every icon loads at its stated
  size (192, 512, maskable 512) plus the iOS icon; the service worker is active and serves the page; with the
  network off the app opens with its thread; a push handed to the service worker (Chrome DevTools' own push
  delivery) is shown as a notification with the right title, body and link; that link opens the thread at the
  message. A real subscription can't be made headless (Chromium without Google's push service says "Registration
  failed"), so:
- Actions > Admin > `push-check` (the deployed function): `send-push` serves the public key that `config.js`
  carries; for a subscription made in the check (its own P-256 key and auth secret) the function returns the
  encrypted request it would send, which the check **decrypts with the subscription's keys** to the exact payload,
  and verifies the VAPID JWT (signature with the public key, audience, expiry, subject); a subscription round-trips
  through `push_subscriptions` with the service key; a demo session can't add a subscription and sees none.
- The only hop not covered is the push service delivering to a real phone: that is the phone check below.

## Check it on your phone

### Android (Chrome)

1. Open `https://vin1764.github.io/ping-dashboard/` in Chrome and sign in.
2. Open it again later (second visit): Ping says **"Install me? …"** with **Install**. Tap it (or Chrome's ⋮ menu >
   **Install app**). The Ping icon appears on your home screen.
3. Open Ping **from the icon**: it opens full screen, without the address bar.
4. Ping asks **"Want me to notify you when something's for you?"**: tap **Yes**, then **Allow**. (Or Profile >
   Notifications > **Turn on**.)
5. Profile > Notifications > **Send a test**: within a few seconds a notification **"Ping · test — Notifications
   work on this device."** appears. Tap it: Ping opens on the chat.
6. Offline: turn on airplane mode, open Ping from the icon: the chat shows with "Offline: your thread as of …".
   Type a question and send: it says "waiting for a connection". Turn airplane mode off: the question is asked and
   answered.
7. The real thing: the next check that brings something for you sends one notification (the title is the
   message's label, e.g. "Reminder · closes tonight 20:00"); tapping it opens the chat at that message.

### iPhone (iOS 16.4 or later, Safari)

1. Open `https://vin1764.github.io/ping-dashboard/` in **Safari** and sign in.
2. On the second visit Ping shows the two taps with a picture; do them: **Share** (the square with the arrow) >
   **Add to Home Screen** > **Add**.
3. Open Ping **from the Home Screen icon** (iOS sends notifications only to apps opened from there).
4. Ping asks **"Want me to notify you…?"**: **Yes**, then **Allow**. (Or Profile > Notifications > **Turn on**.)
5. Profile > Notifications > **Send a test**: a banner **"Ping · test"** appears (also on the lock screen). Tap it:
   Ping opens on the chat.
6. Settings > Notifications > Ping now lists Ping; Focus modes apply to it like any app.
7. Offline and the real thing: as steps 6 and 7 for Android.

### If it doesn't work

- **No "Install" message:** it comes once, on the second visit, and never again after "Not now". Chrome's ⋮ menu >
  Install app (Android) or Share > Add to Home Screen (iPhone) does the same.
- **No notification question on iPhone:** Ping was opened in Safari, not from the Home Screen icon.
- **Profile says "Blocked":** the browser's site settings for `vin1764.github.io` > Notifications > Allow, then
  Profile > Notifications > Turn on.
- **"Send a test" says 0 devices:** turn it off and on again (Profile > Notifications); `push-check` in Admin
  shows whether the function is set up.
- **Nothing at night:** that's quiet hours (outside the check window).

## Privacy

A subscription is an address at your phone's push service (Google's or Apple's) and two public keys; it says
nothing about you. Notifications carry a message's label and first line (what the chat shows), encrypted end to
end: the push service can't read them. Only the owner's devices can subscribe; the demo can't.
