"""The wider mail filter (ping/mail_wide.py), dry-run only for now: made-up mails, no real addresses."""

from datetime import datetime

from ping import mail_wide
from ping.config import IST
from ping.mailbox import Head
from ping.matching import CompanyIndex

INDEX = CompanyIndex([{"company": "JP Morgan Chase & Co"}, {"company": "ZS ASSOCIATES"}, {"company": "Zeta Global"},
                      {"company": "Diageo India Pvt Ltd"}])
NAMES = mail_wide.Names(INDEX)
T = datetime(2026, 11, 20, 10, 0, tzinfo=IST)


def head(sender, subject, bulk=False):
    return Head("1", T, sender, subject, bulk)


def scope(h, **kw):
    return mail_wide.wide_scope(h, INDEX, NAMES, **kw)


def test_company_senders_by_short_names():
    assert scope(head("Campus Recruiting <campus@jpmchase.com>", "Next steps")).because == "company_sender"
    assert scope(head("Talent <talent@zs.com>", "Hello")).company == "ZS ASSOCIATES"


def test_platforms_and_earlier_test_senders():
    assert scope(head("Unstop <noreply@unstop.com>", "Your registration")).because == "platform:unstop"
    assert scope(head("Workday <x@myworkday.com>", "Update")).keep
    assert scope(head("Ops <ops@assess.example>", "Reminder"), test_senders=frozenset({"ops@assess.example"})).keep


def test_job_board_alerts_only_with_a_listed_company_and_a_deadline():
    assert not scope(head("LinkedIn <jobs@linkedin.com>", "30 new jobs for you")).keep
    assert scope(head("Naukri <a@naukri.com>", "Zeta Global hiring: apply by 25 Nov")).because == "job_board_company_deadline"
    h = head("Internshala <a@internshala.com>", "Jobs for you")
    v = scope(h)
    assert not v.keep and v.signal == "body"
    assert not mail_wide.body_decides(h, "Zeta Global is hiring. Great roles.", NAMES, job_board=True).keep
    assert mail_wide.body_decides(h, "Zeta Global is hiring. Last date 25 Nov.", NAMES, job_board=True).keep


def test_a_company_in_the_body_needs_a_placement_word():
    h = head("Someone <a@b.example>", "Hello")
    assert scope(h).signal == "body"
    assert mail_wide.body_decides(h, "Your Diageo interview is on Friday.", NAMES, job_board=False).keep
    assert not mail_wide.body_decides(h, "I bought Diageo shares.", NAMES, job_board=False).keep


def test_never_otp_or_shopping_or_promotions():
    assert not scope(head("Unstop <a@unstop.com>", "Your OTP is 123456")).keep
    assert not scope(head("Shop <a@shop.example>", "Your order has shipped")).keep
    assert not scope(head("News <a@news.example>", "Weekly digest", bulk=True)).keep


def test_a_thread_with_a_kept_mail():
    h = head("Recruiter <r@agency.example>", "Re: your application")
    h.thread = "t1"
    assert scope(h, threads=frozenset({"t1"}), thread_of=lambda x: x.thread).because == "thread"
