# Murang'a County e-Citizen Portal: Backend REST API

A secure REST API that powers digital public services for Murang'a County, Kenya. Residents report issues (broken pipes, potholes, garbage), county staff handle them, and everyone can follow progress.

Built with Django, Django REST Framework, Neon PostgreSQL, Celery with Redis, and the Africa's Talking SMS gateway.

> This folder is the backend of the project. The Next.js frontend lives in the sibling `frontend/` folder (or its own repository).

## Live links

| | |
|---|---|
| Live API (Render) | https://citizen-muranga-portal.onrender.com |
| Live app (frontend, Vercel) | https://muranga-ecitizen-frontend-final.vercel.app/ |
| Local API | http://127.0.0.1:8000/ |
| Local Django admin | http://127.0.0.1:8000/admin/ |

## Demo login credentials

Sign in through the frontend at https://muranga-ecitizen-frontend-final.vercel.app/signin using an email and password:

| Role | Email | Password |
|---|---|---|
| Admin (County Administrator) | kbwaceke@gmail.com | Beth@2026 |
| Officer | beth@muranga.go.ke | mDbzN8R4SdsB#9 |
| Citizen | zachayo@gmail.com | 273bewaki??K# | or create an account as the login as the citizen

The Django admin site (`/admin/`) uses the account's phone number as the username, not the email.

### Important notes before you test

1. **Creating an account or signing in can take 30 to 60 seconds.** The backend runs on the free tier of Render, which puts the service to sleep after a period of inactivity. The first request has to wake it up. The frontend (Vercel) and backend (Render) are also hosted separately, which adds network latency. Please wait for the request to finish. Later requests are much faster.
2. **Email and SMS verification is switched off for now.** New accounts are marked verified automatically, so a resident can sign in right after registering. See "Account verification" below.

## Table of contents

1. [What this API does](#what-this-api-does)
2. [Tech stack](#tech-stack)
3. [Project structure](#project-structure)
4. [Local setup, step by step](#local-setup-step-by-step)
5. [Environment variables](#environment-variables)
6. [Running the project](#running-the-project)
7. [Account verification](#account-verification)
8. [Roles and permissions](#roles-and-permissions)
9. [API reference](#api-reference)
10. [Testing the API with Postman](#testing-the-api-with-postman)
11. [Email and SMS setup](#email-and-sms-setup)
12. [Deployment on Render](#deployment-on-render)
13. [Git workflow](#git-workflow)
14. [Security notes](#security-notes)
15. [Troubleshooting](#troubleshooting)
16. [How the backend was built](#how-the-backend-was-built)

---

## What this API does

- **Role-based access control** for four kinds of users: `CITIZEN`, `STAFF` (field or desk officer), `DEPT_HEAD` (department head) and `ADMIN` (county admin).
- **Login with phone number or email.** The phone number is the account's username field. An email also works, and capital letters in an email do not matter.
- **Account verification and password reset** with 6-digit one-time codes. The code is built and tested, but delivery is switched off in this release (see below).
- **Service requests.** Citizens report issues and follow their progress through a timeline. Officers update the status, and department heads assign officers.
- **Staff management.** Only admins create staff accounts. Staff are deactivated, never deleted, so history stays intact.
- **Announcements** from the county.
- **Audit log.** An append-only trail of what staff did.
- **Privacy.** A citizen can never see or change another citizen's requests.

---

## Tech stack

| Area | Technology |
|---|---|
| Language | Python 3.12 or newer |
| Framework | Django and Django REST Framework (exact versions in `requirements.txt`) |
| Authentication | JWT with `djangorestframework-simplejwt` |
| Database | Neon PostgreSQL through `dj-database-url` |
| Background jobs | Celery with Redis |
| SMS | Africa's Talking (Kenya) |
| Email | Gmail API or Brevo (HTTPS APIs) |
| Audit trail | `django-auditlog` |
| Production server | Gunicorn with WhiteNoise for static files |
| Hosting | Render (free tier) |

---

## Project structure

```text
backend/
├── config/                  # Project settings, URLs, WSGI and Celery setup
│   ├── celery.py
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── apps/
│   ├── users/               # Custom user, roles, login, verification, staff management
│   │   ├── models.py        # User, UserRole, OneTimeCode
│   │   ├── serializers.py
│   │   ├── views.py         # Register, current user
│   │   ├── login.py         # Login by phone or email; blocks unverified citizens only when OTP is on
│   │   ├── otp.py           # Creates, hashes, sends and checks one-time codes
│   │   ├── verification.py  # Verify, forgot password, reset password, change password
│   │   └── staff.py         # Admin staff management
│   ├── categories/          # Departments and service categories
│   ├── service_requests/    # Issue reports, status, assignment, timeline
│   ├── announcements/       # County announcements
│   ├── notifications/       # Alerts and SMS triggers
│   └── audit_logs/          # Audit trail
├── postman/                 # Postman collection for testing every endpoint
│   └── muranga-ecitizen-api.postman_collection.json
├── manage.py
├── Procfile                 # Process definition for deployment
├── requirements.txt
├── .env.example             # Safe template (the real .env is never committed)
└── .gitignore
```

---

## Local setup, step by step

### Prerequisites

- Python 3.12 or newer
- A PostgreSQL database (a free [Neon](https://neon.tech) project works well)
- Redis, only if you want background jobs (see [Running the project](#running-the-project))
- Git

### 1. Clone the repository

```bash
git clone https://github.com/bethkimani/muranga-ecitizen-portal.git
cd muranga-ecitizen-portal/backend
```

### 2. Create and activate a virtual environment

**Windows (PowerShell):**

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

If PowerShell blocks the script, run this once and try again:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

**Linux or macOS:**

```bash
python3 -m venv venv
source venv/bin/activate
```

You should see `(venv)` at the start of your prompt.

### 3. Install the dependencies

```bash
pip install -r requirements.txt
```

### 4. Create your `.env` file

Copy the template and fill in your own values (see [Environment variables](#environment-variables)):

```powershell
Copy-Item .env.example .env
```

### 5. Create the database tables

```bash
python manage.py makemigrations
python manage.py migrate
```

### 6. Create an admin account

```bash
python manage.py createsuperuser
```

This project logs in with the phone number, so enter your phone number (for example `0712345678`) when asked. In the Django admin (`/admin/`), open your user and set **Role** to **County Admin**.

### 7. Add starter data

In the Django admin (`http://127.0.0.1:8000/admin/`), add at least one **Department** and one **Category** (a category belongs to a department). Citizens need a category to file a request.

### 8. Start the server

```bash
python manage.py runserver
```

| What | Address |
|---|---|
| API base | http://127.0.0.1:8000/api/ |
| Health check | http://127.0.0.1:8000/ |
| Django admin | http://127.0.0.1:8000/admin/ |

Opening the health-check address should show `{"service": "Murang'a e-Citizen API", "status": "ok"}`.

---

## Environment variables

Create `backend/.env` (it is ignored by Git). Never commit it.

```dotenv
# Django
SECRET_KEY='replace-with-a-long-random-key'
DEBUG=false
ALLOWED_HOSTS=localhost,127.0.0.1

# Neon PostgreSQL
DATABASE_URL=postgresql://USER:PASSWORD@HOST/DBNAME?sslmode=require

# Africa's Talking (Kenya SMS). Use "sandbox" while developing.
AT_USERNAME=sandbox
AT_API_KEY=

# Redis and Celery
REDIS_URL=redis://localhost:6379/0

# Account verification: 0 = off (current), 1 = on
OTP_REQUIRED=0

# HTTPS email provider (Gmail API; no custom domain required)
GMAIL_CLIENT_ID=
GMAIL_CLIENT_SECRET=
GMAIL_REFRESH_TOKEN=
GMAIL_SENDER=youraddress@gmail.com

# Optional Brevo fallback
BREVO_API_KEY=
BREVO_SENDER_EMAIL=

# Never enable for normal production traffic; temporary test code only
OTP_FIXED_CODE=
ALLOW_FIXED_OTP=0

# Where the frontend runs (used in the links inside emails)
FRONTEND_URL=http://localhost:3000
```

Generate a new secret key with:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Tips:

- Put the `SECRET_KEY` in single quotes, because characters like `%`, `$` and `#` can break `.env` parsing.
- Gmail API credentials are OAuth credentials, not a Gmail password or app password. Grant the `https://www.googleapis.com/auth/gmail.send` scope and set `GMAIL_SENDER` to the same Gmail mailbox authorized by that refresh token (or a Gmail send-as alias).
- For an isolated test only, set `OTP_FIXED_CODE` to six digits and `ALLOW_FIXED_OTP=1`. This makes the same code valid for every account. Remove both settings immediately after testing.
- Restart `runserver` after changing `.env`.

---

## Running the project

You can run the backend alone, or with background jobs and the frontend. Use a separate terminal window for each.

**1. Backend (always)**

```powershell
cd backend
.\venv\Scripts\Activate.ps1
python manage.py runserver
```

**2. Redis (only if you use Celery)**

Redis must be running on the address in `REDIS_URL`. On Windows, the easiest options are Docker (`docker run -p 6379:6379 redis`) or WSL. On Linux or macOS, install and start `redis-server`.

**3. Celery worker (only if emails or SMS go through Celery)**

```powershell
cd backend
.\venv\Scripts\Activate.ps1
celery -A config worker -l info --pool=solo
```

`--pool=solo` is needed on Windows.

**4. Frontend**

```powershell
cd ..\frontend
npm install
npm run dev
```

The frontend runs at http://localhost:3000.

**Useful extra commands**

```bash
python manage.py makemigrations users        # after changing a model
python manage.py migrate                     # apply migrations
python manage.py changepassword 0712345678   # change a user's password (use the phone number)
python manage.py shell                       # open a Django shell
```

---

## Account verification

### Current status: switched off

In this release, email and SMS verification is **not active**. When `OTP_REQUIRED` is unset or `0`:

- A resident who registers is marked verified automatically.
- No email or SMS is sent.
- The resident is sent to the sign-in page and can log in straight away.
- Accounts created earlier that were never verified are also accepted at login.

### Why it is not active yet

1. **Brevo has not verified my account.** Brevo is the email provider used to deliver the codes. Until it approves the account, mail cannot be sent reliably.
2. **A domain name for Murang'a County is needed.** For verification emails to arrive in the inbox instead of the spam folder, they must be sent from an address on a domain the county owns, with SPF and DKIM records set up. A personal Gmail sender address cannot be authenticated this way, so messages from it are likely to be filtered as spam.

The feature is built and will be switched on in a future version once both are in place.

### How it will work when enabled

```text
1. Resident registers            POST /api/auth/register/
        |                        account created, unverified
        v
2. A 6-digit code is sent        by email and SMS
        |
        v
3. Resident confirms the code    POST /api/auth/verify/confirm/
        |                        account marked verified
        v
4. Resident signs in             POST /api/auth/login/
                                 receives access and refresh tokens
```

Rules of the one-time codes:

- The code is stored hashed, never in plain text.
- It expires after 15 minutes.
- A wrong code can be tried 5 times, then it is burned and a new one is needed.
- A new code can be requested once every 60 seconds. Only the newest code works.
- The same mechanism powers forgot password and the admin's "send reset" for staff.
- The email also contains a link to the frontend, `/verify?id=...&code=...`, which verifies automatically.

When enabled, if someone logs in before verifying, the API answers 403 with "Please verify your account first." and the frontend sends them to the verify page.

### Turning it on later

1. Get the Brevo account verified, and set up a county domain with SPF and DKIM.
2. On Render, set `BREVO_API_KEY` and `BREVO_SENDER_EMAIL` (an address on the county domain), and set `OTP_REQUIRED=1`.
3. In the frontend, restore `OTP_REQUIRED` in `src/api/auth.ts` (see the frontend README).
4. Redeploy both services.

Staff accounts created by an admin are verified automatically.

---

## Roles and permissions

| Action | Citizen | Officer (`STAFF`) | Dept head (`DEPT_HEAD`) | Admin (`ADMIN`) |
|---|:--:|:--:|:--:|:--:|
| Register and log in | Yes | Yes | Yes | Yes |
| Create a service request | Yes | | | |
| See own requests | Yes | | | |
| See requests of own department | | Yes | Yes | Yes |
| Change a request's status | No | Yes | Yes | Yes |
| Assign an officer to a request | No | No | Yes | Yes |
| Manage staff accounts | No | No | No | Yes |
| Read the audit log | No | No | No | Yes |
| Create announcements | No | | | Yes |

Other rules enforced by the API:

- Nobody can give themselves a role at registration. Anyone who registers is a `CITIZEN`, even if they send `"role": "ADMIN"`.
- Staff cannot be created with the `CITIZEN` role, and a temporary password is required.
- Admins cannot deactivate their own account.
- A deactivated staff member can no longer log in.

---

## API reference

Base URL (live): `https://citizen-muranga-portal.onrender.com`
Base URL (local): `http://127.0.0.1:8000`

Protected endpoints need this header, where the token comes from the login response:

```text
Authorization: Bearer <access_token>
```

### Authentication

| Method | Endpoint | Auth | Purpose |
|---|---|---|---|
| POST | `/api/auth/register/` | None | Create a citizen account |
| POST | `/api/auth/verify/send/` | None | Send (or resend) a verification code when `OTP_REQUIRED=1` |
| POST | `/api/auth/verify/confirm/` | None | Confirm the code when `OTP_REQUIRED=1` |
| POST | `/api/auth/login/` | None | Log in with phone or email, returns `access` and `refresh` |
| POST | `/api/auth/refresh/` | None | Exchange a refresh token for a new access token |
| GET | `/api/auth/me/` | Token | Current user's profile |
| POST | `/api/auth/password/forgot/` | None | Send a password reset code (needs email delivery) |
| POST | `/api/auth/password/reset/` | None | Set a new password with the code |
| POST | `/api/auth/change-password/` | Token | Change password while signed in |

Example login bodies. All three work:

```json
{ "identifier": "0712345678", "password": "StrongPass123!" }
{ "identifier": "name@example.com", "password": "StrongPass123!" }
{ "phone_number": "0712345678", "password": "StrongPass123!" }
```

Phone numbers like `+254712345678` and `0712 345 678` are normalised to `0712345678`.

### Reference data

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/departments/` and `/api/departments/{id}/` | County departments |
| GET | `/api/categories/` and `/api/categories/{id}/` | Service categories |

### Service requests

| Method | Endpoint | Who | Purpose |
|---|---|---|---|
| GET | `/api/requests/` | Any signed-in user | List requests (citizens see only their own) |
| POST | `/api/requests/` | Citizen | Create a request |
| GET | `/api/requests/{id}/` | Owner or staff | Request details with timeline |
| PATCH | `/api/requests/{id}/` | Depends on rules | Edit a request |
| DELETE | `/api/requests/{id}/` | Depends on rules | Delete a request |
| POST | `/api/requests/{id}/status/` | Staff | Set status, for example `In Progress` |
| POST | `/api/requests/{id}/assign/` | Dept head, admin | Assign an officer |

Create a request:

```json
{
  "title": "Burst pipe",
  "description": "Water flowing onto the road",
  "category": 1,
  "sub_county": "Kiharu",
  "ward": "Township",
  "landmark": "Near the market"
}
```

Set a status:

```json
{ "status": "In Progress", "note": "On site" }
```

Assign an officer:

```json
{ "officer": 5 }
```

### Staff management (admin only)

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/staff/` | List staff |
| POST | `/api/staff/` | Create a staff, head or admin account |
| GET / PATCH | `/api/staff/{id}/` | View or update a staff member |
| DELETE | `/api/staff/{id}/` | Deactivate (not delete) a staff member |
| POST | `/api/staff/{id}/send-reset/` | Email and SMS a password reset code |

Create a staff member:

```json
{
  "first_name": "Test",
  "last_name": "Officer",
  "email": "officer1@muranga.go.ke",
  "phone_number": "0731234567",
  "role": "STAFF",
  "department": 1,
  "password": "StrongPass123!"
}
```

The admin chooses a temporary password. The admin never sees the user's real password once the staff member resets it.

### Other

| Method | Endpoint | Purpose |
|---|---|---|
| GET / POST | `/api/announcements/` | List or create announcements (create is admin only) |
| GET | `/api/audit-logs/` | Audit trail (admin only) |

---

## Testing the API with Postman

A ready-made collection with 88 requests and automatic tests is in `postman/muranga-ecitizen-api.postman_collection.json`.

### 1. Import it

Postman, then **Import**, then choose the file. (If the file will not open, use **Import, Raw text** and paste its contents.)

### 2. Set the variables

Open the collection, then the **Variables** tab, and set:

| Variable | Value |
|---|---|
| `baseUrl` | `http://127.0.0.1:8000` locally, or `https://citizen-muranga-portal.onrender.com` for the live API |
| `adminPhone` | Phone number of your County Admin account |
| `adminPassword` | That account's password (never commit this) |

Make sure at least one department and one category exist.

### 3. Run it

Start the backend, then right-click the collection and choose **Run**. Run the folders from top to bottom. Tokens and IDs are saved automatically between requests.

Note: with verification switched off, the requests that expect a 403 before verifying, or that need a verification code, will not behave as in the table below. Those checks apply only when `OTP_REQUIRED=1`.

### 4. One-time codes (only when `OTP_REQUIRED=1`)

Three requests need a code that the backend printed in the `runserver` terminal (or emailed):

| Variable | Used by |
|---|---|
| `verifyCode` | "Confirm verification: real code" (citizen A) |
| `verifyCodeB` | "Confirm verification for B" (citizen B) |
| `resetCode` | "Reset with real code" (password reset) |

Copy the newest 6-digit code into the variable, then run that request.

### What the folders check

| Folder | What it tests |
|---|---|
| 0. Health | API is up |
| 1. Reference data | Departments and categories (and saves their IDs) |
| 2. Auth: citizen A | Register, duplicates, login, refresh, `me` |
| 3. Service requests | Create, list, open, edit, and that citizens cannot resolve requests, list staff or read the audit log |
| 4. Citizen B | Privilege escalation attempt at registration, and that B cannot see, edit or delete A's data |
| 5. Admin | Admin login, create officer and department head, validation errors, send reset |
| 6. Officer and head | Status changes, assignment rules, timeline |
| 7. Announcements | Create, update and delete, and citizen restrictions |
| 8. Password recovery | Forgot, reset, change password |
| 9. Cleanup | Deactivate test staff and confirm they cannot log in |

### Expected results

| Check | Expected status |
|---|---|
| Register a new citizen | `201` |
| Register the same phone again | `400` |
| Log in before verifying (only when `OTP_REQUIRED=1`) | `403` |
| Wrong verification code (only when `OTP_REQUIRED=1`) | `400` |
| Wrong password at login | `401` |
| `/api/auth/me/` with no token | `401` |
| Citizen opens `/api/staff/` | `403` |
| Citizen B opens citizen A's request | `403` or `404` |
| Officer assigns a request | `403` |
| Invalid status such as `Nonsense` | `400` |
| Admin deactivates staff | `204` |

### Quick manual test without the collection

1. `POST /api/auth/register/` with a phone, username, email and password.
2. `POST /api/auth/login/` and copy the `access` token.
3. `POST /api/requests/` with that token in the `Authorization` header.

> Some announcement fields and the "admin cannot deactivate own account" check depend on your serializers and IDs. Adjust those requests if they fail.

---

## Email and SMS setup

This section is for when verification is switched on in a future version.

### Email

Two HTTPS providers are supported. Gmail is tried first, then Brevo.

**Brevo (planned primary provider)**

1. Get the Brevo account verified.
2. Create an API key and add a sender address.
3. Set `BREVO_API_KEY` and `BREVO_SENDER_EMAIL` on Render.
4. A Brevo response of 201 means Brevo accepted the request. It does not prove the message reached an inbox. Check Brevo's transactional logs.
5. To reach the inbox instead of spam, send from an address on a county-owned domain with SPF and DKIM authenticated. This needs the Murang'a County domain name.

**Gmail API (optional)**

1. In Google Cloud, create a project, enable the Gmail API, and configure the OAuth consent screen.
2. Create OAuth credentials and authorize the sender mailbox with the `https://www.googleapis.com/auth/gmail.send` scope.
3. Set `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_REFRESH_TOKEN` and `GMAIL_SENDER` on Render.
4. For an OAuth consent screen left in Testing, Google can expire refresh tokens after seven days.

Do not put OAuth secrets or tokens in source control or logs.

### SMS (Africa's Talking)

1. Sign up at https://africastalking.com and open the Sandbox app.
2. Go to **Settings, API Key** and generate a key.
3. Put `AT_USERNAME=sandbox` and `AT_API_KEY=<key>` in `.env`.
4. Open the Simulator from the dashboard to read the messages.

The sandbox never sends to real phones. To reach real residents you need a live Africa's Talking app with credit and a live username. Without an API key, SMS messages are skipped and a warning is logged.

---

## Deployment on Render

Live API: https://citizen-muranga-portal.onrender.com

### Create the service

1. Push the repository to GitHub.
2. On https://render.com create a **Web Service** from the repository and set the **Root Directory** to `backend`.
3. Use these commands:

**Build command**

```bash
pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate
```

**Start command**

```bash
gunicorn config.wsgi:application
```

### Environment variables on Render

Add these in the service's **Environment** tab. Your local `.env` is not uploaded.

| Variable | Value |
|---|---|
| `SECRET_KEY` | A new, long random key |
| `DEBUG` | `false` |
| `ALLOWED_HOSTS` | Your Render hostname, for example `citizen-muranga-portal.onrender.com` |
| `DATABASE_URL` | Your Neon connection string |
| `OTP_REQUIRED` | Unset or `0` (verification off, current). `1` turns verification on. |
| `FRONTEND_URL` | `https://muranga-ecitizen-frontend-final.vercel.app` |
| `AT_USERNAME`, `AT_API_KEY` | Africa's Talking credentials (optional while verification is off) |
| `REDIS_URL` | A hosted Redis URL (only if you use Celery) |
| `BREVO_API_KEY`, `BREVO_SENDER_EMAIL` | Brevo HTTPS provider (needed when verification is switched on) |
| `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_REFRESH_TOKEN`, `GMAIL_SENDER` | Optional Gmail API sender |
| `OTP_FIXED_CODE`, `ALLOW_FIXED_OTP` | Temporary OTP testing only; remove after testing |

Also add the live frontend address to your CORS allowed origins in `settings.py`.

Turning verification off reduces account security, because anyone can create an account with an email address or phone number they do not own. It is acceptable for this demonstration release, and verification will be restored in a future version.

### Free-tier behaviour

Render's free tier puts the service to sleep after a period without traffic. The first request afterwards (including creating an account or signing in) can take 30 to 60 seconds while the service starts. The frontend and backend are also hosted on different platforms, which adds some latency to every request. A paid plan keeps the service awake and removes the long first request.

### After the first deploy

1. Open the Render **Shell** and create the admin: `python manage.py createsuperuser`.
2. Visit the live address. You should see the `{"status": "ok"}` health check.
3. In Postman, change `baseUrl` to the live address and run the collection again.

---

## Git workflow

Each piece of work gets its own branch and pull request:

```bash
git checkout main
git pull
git checkout -b feature/backend-account-verification
git add backend
git commit -m "Add one-time-code account verification and password reset"
git push -u origin feature/backend-account-verification
```

Then open a pull request into `main`. Merge the backend pull request before the frontend one, because the frontend pages call the new endpoints.

`.env` files, `venv/`, `__pycache__/` and similar are ignored by `backend/.gitignore`.

---

## Security notes

- **Secrets stay out of Git.** `.env` is ignored. Only `.env.example` is committed, with no real values.
- **Demo accounts.** The credentials at the top of this file are for reviewing the project. Change these passwords after the review.
- **If a secret is ever shared or committed,** rotate it: reset the Neon password and generate a new `SECRET_KEY`.
- **One-time codes are hashed**, expire, are single-use and limited to 5 attempts.
- **No account probing.** Forgot-password and send-code answer the same way whether or not the account exists.
- **Passwords** are validated with Django's password rules and stored hashed.
- **Role escalation is blocked.** Roles cannot be chosen at registration.
- **Data isolation.** Citizens can only reach their own requests.
- **Accounts are deactivated, not deleted,** so the audit trail stays intact.
- Use long, unique passwords for admin accounts.

---

## Troubleshooting

| Problem | Likely cause and fix |
|---|---|
| First request takes 30 to 60 seconds | Free-tier cold start on Render. Wait for it to finish; later requests are fast. |
| Login returns `403` | Only happens when `OTP_REQUIRED=1` and the account is not verified. Set `OTP_REQUIRED` to `0`, or verify the account. |
| Login returns `401` | Wrong credentials, or the staff account was deactivated. |
| Verify page appears after registering | The frontend still has verification on. Check `OTP_REQUIRED` in `src/api/auth.ts` and redeploy. |
| Verify-send returns `429` | A code was generated in the last 60 seconds. Wait for the countdown and retry. |
| Brevo returns 201 but no email arrives | Check Brevo transactional logs, account status, suppression list and sender authentication. A 201 is provider acceptance, not inbox delivery. |
| Emails land in spam | Send from an authenticated county domain (SPF and DKIM). A free personal address cannot be authenticated. |
| Gmail API reports `invalid_grant` | Reauthorize the sender mailbox and replace the refresh token. |
| `SSL: WRONG_VERSION_NUMBER` when sending SMS | A proxy, VPN or antivirus is interfering. Clear `HTTPS_PROXY` and `HTTP_PROXY`, or leave `AT_API_KEY` empty. |
| SMS not arriving on a phone | The Africa's Talking sandbox only logs messages in the simulator. |
| Africa's Talking `401` | Sandbox keys only work with the username `sandbox`. Check for stray spaces in the key. |
| `No installed app with label 'users'` | Check the app's `name` and `label` in `apps/users/apps.py`. |
| Celery cannot connect | Redis is not running, or `REDIS_URL` is wrong. Use `--pool=solo` on Windows. |
| Browser shows a CORS error | Add the frontend address to the CORS allowed origins. |
| Changes in `.env` ignored | Restart `runserver` and the Celery worker. |

---

## How the backend was built

1. **Project and apps.** A Django project (`config`) with modular apps: `users`, `categories`, `service_requests`, `announcements`, `notifications`, `audit_logs`.
2. **Custom user model.** `User` extends `AbstractUser` with a `role`, a unique `phone_number` (used as the login field), `home_ward`, `sub_county`, `is_phone_verified` and a `department`. A case-insensitive unique constraint allows only one account per email address.
3. **JWT authentication.** Login and refresh endpoints using `djangorestframework-simplejwt`.
4. **Flexible login.** A custom serializer accepts a phone number or an email as `identifier`, normalises `+254...` phone numbers, and keeps the older `phone_number` field working.
5. **Reference data.** Departments and categories exposed as read-only lists.
6. **Service requests.** Create, list and detail with reference numbers, a `Pending` starting status, a timeline, status changes and officer assignment. Citizens only see their own requests.
7. **Staff management.** Admin-only API to create, update and deactivate staff, with role validation and an audit mixin.
8. **Audit logs.** An append-only record of actions, readable only by admins.
9. **Announcements** for county notices.
10. **One-time codes.** A `OneTimeCode` model plus `otp.py` and `verification.py` for account verification, forgot password, reset and change password, with hashed codes, expiry, attempt limits and a resend cooldown. Switched off by default in this release through `OTP_REQUIRED`.
11. **Delivery.** Codes go out by email (Gmail API or Brevo HTTPS) and SMS (Africa's Talking), with a local-only console fallback for development.
12. **Login protection.** When verification is on, unverified citizens are blocked at login with a clear message.
13. **Testing.** A PowerShell smoke-test script and the Postman collection that cover public, citizen, privacy, officer, head and admin behaviour.
14. **Repository hygiene.** A backend `.gitignore`, a `.env.example` template, feature branches and pull requests.
15. **Deployment.** Gunicorn and WhiteNoise on Render with Neon PostgreSQL.

---

## License and contact

Built for Murang'a County as a digital public service project.

kbwaceke@gmail.com
0112280703