// "send-push": Ping's Web Push sender (docs/PUSH.md). The VAPID private key lives only here, as a Supabase function
// secret (VAPID_PRIVATE_KEY); the public key is in the dashboard's config.js. Subscriptions are rows of
// push_subscriptions (owner-only by Row Level Security; this function reads them with the service key).
//
//   POST {mode: "notify", id, title, body, url, tag}   the hourly run (service key): one notification, at most once per id
//   POST {mode: "due"}                                 pg_cron every 5 min (shared secret): reminders whose time has come
//   POST {mode: "test"}                                the owner (their login): "notifications work on this device"
//   POST {mode: "dry", subscription, payload}          checks (service key): the encrypted request, not sent
//   GET                                                the public key (also in config.js)
// Nothing is sent in quiet hours: outside the student's check window (profile check_from..check_to, IST).
import webpush from "npm:web-push@3.6.7";
import { createClient } from "npm:@supabase/supabase-js@2.45.4";
import { caller, cors, json } from "../_shared/owner.ts";
import { quiet, reminderBody } from "./rules.ts";

const PUBLIC = Deno.env.get("VAPID_PUBLIC_KEY") || "";
const PRIVATE = Deno.env.get("VAPID_PRIVATE_KEY") || "";
const SUBJECT = Deno.env.get("VAPID_SUBJECT") || "https://example.com/ping";
const TTL = 6 * 3600;           // a notification older than 6 h isn't worth showing

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  if (req.method === "GET") return json({ publicKey: PUBLIC || null });
  if (!PUBLIC || !PRIVATE) return json({ error: "push is not set up (Actions > Admin > push-setup)" }, 500);
  webpush.setVapidDetails(SUBJECT, PUBLIC, PRIVATE);
  const svcKey = Deno.env.get("PING_SERVICE_KEY") || "";
  const cron = Deno.env.get("PING_CRON_SECRET") || "";
  const isService = !!svcKey && (req.headers.get("authorization") === `Bearer ${svcKey}`);
  const isCron = !!cron && req.headers.get("x-ping-cron") === cron;
  const body = await req.json().catch(() => ({}));
  const mode = String(body?.mode || "");
  const svc = createClient(Deno.env.get("SUPABASE_URL")!, svcKey);

  // the owner's check window, for quiet hours
  const window = async () => (await svc.from("profile").select("check_from,check_to").eq("id", 1).limit(1)).data?.[0] || {};
  const subs = async () => (await svc.from("push_subscriptions").select("endpoint,p256dh,auth")).data || [];
  async function sendAll(payload: Record<string, unknown>) {
    const list = await subs();
    let ok = 0, gone = 0, failed = 0;
    for (const s of list) {
      try {
        await webpush.sendNotification({ endpoint: s.endpoint, keys: { p256dh: s.p256dh, auth: s.auth } },
          JSON.stringify(payload), { TTL, urgency: "high" });
        ok++;
        await svc.from("push_subscriptions").update({ last_ok_at: new Date().toISOString(), failures: 0 }).eq("endpoint", s.endpoint);
      } catch (e) {
        const code = (e as { statusCode?: number }).statusCode || 0;
        if (code === 404 || code === 410) { gone++; await svc.from("push_subscriptions").delete().eq("endpoint", s.endpoint); }
        else { failed++; console.error(JSON.stringify({ event: "push_failed", status: code, error: String((e as Error).message).slice(0, 200) })); }
      }
    }
    return { devices: list.length, ok, gone, failed };
  }

  if (mode === "dry" && isService) {
    // the request a push service would get (encrypted body, VAPID JWT): for the headless check, nothing is sent
    const r = webpush.generateRequestDetails(body.subscription, JSON.stringify(body.payload || {}), { TTL, urgency: "high" });
    return json({ endpoint: r.endpoint, headers: r.headers, body: btoa(String.fromCharCode(...new Uint8Array(r.body))) });
  }

  if (mode === "test") {
    const who = await caller(req);
    if (who?.role !== "owner") return json({ error: "only the owner's devices get notifications" }, 403);
    const res = await sendAll({ title: "Ping · test", body: "Notifications work on this device.", url: "./#chat", tag: "ping-test",
                                at: new Date().toISOString() });
    console.log(JSON.stringify({ event: "push_test", ...res }));
    return json(res);
  }

  if (mode === "notify" && isService) {
    const id = String(body.id || "");
    if (!id || !body.title) return json({ error: "id and title are needed" }, 400);
    if (quiet(new Date(), await window())) {
      console.log(JSON.stringify({ event: "push_quiet", id }));
      return json({ sent: false, why: "quiet hours" });
    }
    // once per message: the queue keeps what was sent
    const { data: had } = await svc.from("push_queue").select("id").eq("id", `run:${id}`).limit(1);
    if (had?.length) return json({ sent: false, why: "already sent" });
    const payload = { title: body.title, body: body.body || "", url: body.url || "./#chat", tag: body.tag || id, at: new Date().toISOString() };
    const res = await sendAll(payload);
    await svc.from("push_queue").upsert({ id: `run:${id}`, kind: "run", title: payload.title, body: payload.body, url: payload.url,
      tag: payload.tag, send_at: payload.at, sent_at: payload.at, result: JSON.stringify(res) });
    console.log(JSON.stringify({ event: "push_sent", kind: "run", ...res }));
    return json({ sent: res.ok > 0, ...res });
  }

  if (mode === "due" && (isCron || isService)) {
    const now = new Date();
    if (quiet(now, await window())) return json({ sent: 0, why: "quiet hours" });
    const { data: due } = await svc.from("push_queue").select("*").is("sent_at", null).lte("send_at", now.toISOString())
      .order("send_at").limit(10);
    let sent = 0;
    for (const q of due || []) {
      // a reminder for a test that has already started is dropped, not sent late
      if (q.event_at && new Date(q.event_at) <= now) {
        await svc.from("push_queue").update({ sent_at: now.toISOString(), result: "skipped: the test had started" }).eq("id", q.id);
        continue;
      }
      // a form you've ticked since the reminder was queued: not sent (your own ticks only, never a demo session's)
      if (q.form_key) {
        const { data: tick } = await svc.from("form_status").select("filled").eq("form_key", q.form_key).eq("is_demo", false).eq("filled", true).limit(1);
        if (tick?.length) {
          await svc.from("push_queue").update({ sent_at: now.toISOString(), result: "skipped: the form is ticked as filled" }).eq("id", q.id);
          continue;
        }
      }
      const res = await sendAll({ title: q.title, body: reminderBody(q.body, q.event_at, now), url: q.url || "./#chat",
                                  tag: q.tag || q.id, at: now.toISOString() });
      await svc.from("push_queue").update({ sent_at: now.toISOString(), result: JSON.stringify(res) }).eq("id", q.id);
      sent += res.ok > 0 ? 1 : 0;
      console.log(JSON.stringify({ event: "push_sent", kind: q.kind, ...res }));
    }
    return json({ sent, due: due?.length || 0 });
  }
  return json({ error: "not allowed" }, 403);
});
