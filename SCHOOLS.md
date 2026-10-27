# Schools (institution plan)

How schools work on LuminaIQ, and what to set up before switching it on.

## Lifecycle

1. A school admin signs up normally, opens **Institution** and requests access.
   The school starts as **waiting for approval** and nothing works yet.
2. A LuminaIQ platform admin opens **/platform** and approves it. Approval starts
   the free trial (`INSTITUTION_TRIAL_DAYS`, 25 seats) unless the school already paid.
3. The school pays for seats with Razorpay for 1, 3, 6 or 12 months. The term runs
   from the payment date; paying early adds the new term after the current end date.
4. A school works only while it is **approved and paid up**. When the term ends, or
   we pause it in /platform, school-created students can't sign in or use the API
   (403 `school_inactive`) and everyone else falls back to the Free plan. This needs
   no cron: the end date is checked on every request (cached for a minute). An hourly
   sweep only relabels the school as `expired` for reporting.

Offline payments (bank transfer, cheque): /platform → **Extend** adds days and seats
and notes the reference. Every approval, pause, payment and password reset is in the
school's **History** (`institution_audit`).

## Student sign-ins

Staff create accounts under **Institution → Student accounts**, one at a time or from
a CSV (`name, reg_no, password, class`, up to 500 per upload).

- ID: `<studentname>-<last 2 digits of register number>@luminaiq.fun`, e.g.
  Arun Kumar, 21CS107 → `arunkumar-07@luminaiq.fun`. This is only a sign-in name: no
  mailbox exists and no email is ever sent.
- IDs are unique across every school. On a clash a number is added to the name part:
  `arunkumar-07`, `arunkumar2-07`, `arunkumar3-07`. Staff can also type an ID by hand.
- The school sets the password (or one is generated). It is shown once, with a CSV
  download. The student must choose their own password at first sign-in, and can
  change it any time in Settings → Password.
- Forgotten password: staff press **Reset password** and hand over the new one.
- Admins can switch a student's account off (frees the seat, keeps their work) and
  back on. Nobody can sign up with an `@luminaiq.fun` address themselves.

Students can still join with a class code using their own account, as before.

## Setup

1. Run `backend/migrations/014_school_accounts_and_approval.sql` in Supabase (SQL
   editor). Schools that already exist are marked approved so they keep working.
2. Backend environment:

   | Variable | Value |
   | --- | --- |
   | `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET` | `rzp_test_...` keys for test mode, `rzp_live_...` for real payments |
   | `RAZORPAY_WEBHOOK_SECRET` | secret of the webhook below |
   | `PLATFORM_ADMIN_EMAILS` | comma-separated emails allowed into /platform (or give them `owner`/`admin` in `user_roles`) |
   | `INSTITUTION_REQUIRE_APPROVAL` | `true` (default) |
   | `INSTITUTION_TRIAL_DAYS` | `14` (default; `0` = pay first) |
   | `STUDENT_LOGIN_DOMAIN` | `luminaiq.fun` (default) |

3. Razorpay Dashboard → Webhooks (create it once in Test Mode and once in Live Mode):
   URL `https://<backend>/api/v1/billing/webhook`, events `payment.captured`,
   `order.paid`, `payment.failed` and the `subscription.*` events. The webhook is the
   backup if a school closes the browser before the payment is confirmed.
4. Supabase Auth: the password policy must accept 8+ characters with a letter and a
   number (what the school UI asks for).

## Scale and isolation

- Every school action is scoped by the caller's membership; class and student ids
  from a request are always checked against the caller's school.
- Lookups that grow with school size are batched (class dashboard: 3 queries per
  class instead of 3 per student; lists are paged and chunked).
- Per-request gate checks are cached in-process for 60 s.
- Indexes for per-school lookups are in migration 014.

## Tests

```
cd backend && pip install pytest && python -m pytest tests
```
