"""Mail rules v3 (ping/mail_source.py scope, ping/mail_names.py): made-up mails in the shape of the 24 Nov 30-day dry
run on the real mailbox, which found ICICI Bank read as ICICI Lombard, ".info" as Info Edge, "futures" as Futures
First, Unstop newsletters as test invites, Swiggy / Angel One / Naukri bulk mail as placement mail."""

from datetime import datetime

from ping import mail_source
from ping.config import IST
from ping.mailbox import Head
from ping.matching import CompanyIndex

INDEX = CompanyIndex([{"company": c} for c in (
    "JP Morgan Chase & Co", "ZS ASSOCIATES", "Zeta Global", "Diageo India Pvt Ltd", "ICICI LOMBARD",
    "Futures First Info Services Pvt. Ltd", "INFO EDGE INDIA LIMITED", "Sun Valley Investment Group",
    "EY Global Delivery Services India LLP", "Swiggy Limited")])
T = datetime(2026, 11, 20, 10, 0, tzinfo=IST)


def head(sender, subject, bulk=False, thread=None):
    return Head("1", T, sender, subject, bulk, thread)


def scope(h, **kw):
    return mail_source.scope(h, INDEX, **kw)


def test_a_company_by_its_own_domain_or_full_name():
    assert scope(head("Campus Recruiting <campus@jpmchase.com>", "Next steps")).company == "JP Morgan Chase & Co"
    assert scope(head("Talent <talent@zs.com>", "Hello")).company == "ZS ASSOCIATES"
    assert scope(head("A Recruiter <a.r@in.ey.com>", "Next steps")).company == "EY Global Delivery Services India LLP"
    assert scope(head("x <a@b.example>", "Futures First: your next round")).company == "Futures First Info Services Pvt. Ltd"


def test_never_a_parent_company_or_a_first_word_alone():
    assert not scope(head("ICICI Bank <alerts@custcomm.icici.bank.in>", "Your statement")).keep
    assert not scope(head("Finlatics <hi@finlatics.info>", "Free course")).keep
    assert not scope(head("ABC - Aditya Birla Sun Life Mutual Fund <x@camsonline.com>", "NAV update")).keep
    h = head("Traders Watch <x@broker.example>", "Market outlook")
    v = scope(h)
    assert not v.keep and v.signal == "body"
    assert not mail_source.body_decides(h, "Futures and options: an interview with our analyst.", [], INDEX, "body").keep
    assert mail_source.body_decides(h, "Your Futures First interview is on Friday.", [], INDEX, "body").keep


def test_bulk_is_never_kept_unless_the_placement_office_or_a_platform_with_a_test_link():
    assert not scope(head("Naukri Campus <jobs@naukri.com>", "Zeta Global hiring: apply by 25 Nov", bulk=True)).keep
    assert not scope(head("Swiggy <noreply@swiggy.in>", "Interview tips and 50% off", bulk=True)).keep
    assert not scope(head("Angel One <research@angelbroking.in>", "Diageo results: interview", bulk=True)).keep
    assert not scope(head("Diageo Careers <news@diageo.com>", "Interview season")).keep            # a newsletter sender
    assert scope(head("Training & Placement Cell <tnp@inst.example>", "Weekly update", bulk=True)).keep
    v = scope(head("Team Unstop <hi@unstop.news>", "Top 10 challenges this week"))
    assert not v.keep
    v = scope(head("HackerRank <support@hackerrank.com>", "Invitation: online assessment", bulk=True))
    assert not v.keep and v.signal == "test_link"
    h = head("HackerRank <support@hackerrank.com>", "Invitation: online assessment", bulk=True)
    assert mail_source.body_decides(h, "", ["https://www.hackerrank.com/tests/abc-123"], INDEX, "test_link").keep
    assert not mail_source.body_decides(h, "", ["https://www.hackerrank.com/blog/top-10"], INDEX, "test_link").keep


def test_platforms_earlier_test_senders_and_threads():
    assert scope(head("Unstop <noreply@unstop.com>", "Your registration for the Diageo case challenge")).keep
    assert scope(head("Workday <x@myworkday.com>", "Application update")).keep
    assert scope(head("Ops <ops@assess.example>", "Reminder"), test_senders=frozenset({"ops@assess.example"})).keep
    assert scope(head("Recruiter <r@agency.example>", "Re: next steps", thread="t1"), threads=frozenset({"t1"})).because == "thread"
    assert scope(head("Me <me@inst.example>", "My application"), me="me@inst.example").because == "yours"


def test_never_otp_shopping_or_job_boards():
    assert not scope(head("Unstop <a@unstop.com>", "Your OTP is 123456")).keep
    assert not scope(head("Shop <a@shop.example>", "Your order has shipped")).keep
    assert not scope(head("LinkedIn <jobs@linkedin.com>", "Diageo is hiring")).keep
