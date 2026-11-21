"""The dashboard login check, against a fake Supabase."""

import ping.authcheck as ac


class R:
    def __init__(self, code, data=None, text=""):
        self.status_code, self._d, self.text = code, data or {}, text

    def json(self):
        return self._d


def test_reports_project_users_and_missing_mail_address(monkeypatch):
    def fake_get(url, params=None, headers=None, timeout=None):
        if url.endswith("/auth/v1/settings"):
            return R(200, {"external": {"email": True}, "disable_signup": True, "mailer_autoconfirm": False})
        return R(200, {"users": [{"email": "Someone@Kgpian.iitkgp.ac.in", "email_confirmed_at": "x",
                                  "identities": [{"provider": "email"}], "last_sign_in_at": None}]})
    monkeypatch.setattr(ac.requests, "get", fake_get)
    lines = ac.check_dashboard_auth("https://abcd1234.supabase.co", "sb_secret_x", "sb_publishable_abcdefghij",
                                    "me@kgpian.iitkgp.ac.in")
    text = "\n".join(lines)
    assert "abcd1234" in text and "SAME project" in text and "email sign-in enabled        : True" in text
    assert "So***@Kgpian.iitkgp.ac.in" in text and "capitals" in text
    assert "is NOT a user in this project" in text
    assert "sb_secret_x" not in text


def test_reports_key_from_another_project(monkeypatch):
    monkeypatch.setattr(ac.requests, "get", lambda url, **k: R(401, text='{"message":"Invalid API key"}')
                        if url.endswith("/settings") else R(200, {"users": []}))
    text = "\n".join(ac.check_dashboard_auth("https://abcd.supabase.co", "s", "sb_publishable_zz", "me@x.in"))
    assert "REJECTED (HTTP 401" in text
