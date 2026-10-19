#  Murang'a County e-Citizen Portal: Backend REST API

A secure REST API that powers digital public services for Murang'a County, Kenya. Residents report issues (broken pipes, potholes, garbage), county staff handle them, and everyone is kept informed by email and SMS.

Built with **Django**, **Django REST Framework**, **Neon PostgreSQL**, **Celery + Redis** and the **Africa's Talking** SMS gateway.

> This folder is the backend of the project. The Next.js frontend lives in the sibling `frontend/` folder.

---

##  Table of contents

1. [What this API does](#-what-this-api-does)
2. [Tech stack](#-tech-stack)
3. [Project structure](#-project-structure)
4. [Local setup, step by step](#-local-setup-step-by-step)
5. [Environment variables](#-environment-variables)
6. [Running the project](#-running-the-project)
7. [How account verification works](#-how-account-verification-works)
8. [Roles and permissions](#-roles-and-permissions)
9. [API reference](#-api-reference)
10. [Testing the API with Postman](#-testing-the-api-with-postman)
11. [Email and SMS setup](#-email-and-sms-setup)
12. [Deployment on Render](#-deployment-on-render)
13. [Git workflow](#-git-workflow)
14. [Security notes](#-security-notes)
15. [Troubleshooting](#-troubleshooting)
16. [How the backend was built](#-how-the-backend-was-built)

---

## What this API does

* **Role-based access control** for four kinds of users: `CITIZEN`, `STAFF` (field or desk officer), `DEPT_HEAD` (department head) and `ADMIN` (county admin).
* **Login with phone number or email.** The phone number is the account's username field; an email also works, and capitals in an email don't matter.
* **Account verification and password reset** with 6-digit one-time codes, sent by email and SMS.
* **Service requests.** Citizens report issues and follow their progress through a timeline. Officers update the status, and department heads assign officers.
* **Staff management.** Only admins create staff accounts. Staff are deactivated, never deleted, so history stays intact.
* **Announcements** from the county.
* **Audit log.** An append-only trail of what staff did.
* **Privacy.** A citizen can never see or change another citizen's requests.

---

##  Tech stack

| Area | Technology |
|---|---|
| Language | Python 3.12 or newer |
| Framework | Django and Django REST Framework (exact versions in `requirements.txt`) |
| Authentication | JWT with `djangorestframework-simplejwt` |
| Database | Neon PostgreSQL through `dj-database-url` |
| Background jobs | Celery with Redis |
| SMS | Africa's Talking (Kenya) |
| Audit trail | `django-auditlog` |
| Production server | Gunicorn with WhiteNoise for static files |
| Hosting | Render |

---

## 📁 Project structure

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
│   │   ├── login.py         # Login by phone or email, blocks unverified citizens
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
├── .env             # Safe template (the real .env is never committed)
└── .gitignore
```

---

##  Local setup, step by step

### Prerequisites

* Python 3.12 or newer
* A PostgreSQL database (a free [Neon](https://neon.tech) project works well)
* Redis, only if you want background jobs (see [Running the project](#-running-the-project))
* Git

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

Copy the template and fill in your own values (see [Environment variables](#-environment-variables)):

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

This project logs in with the **phone number**, so enter your phone number (for example `0712345678`) when asked. In the Django admin (`/admin/`), open your user and set **Role** to **County Admin**.

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

##  Environment variables

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

# Email (Gmail SMTP). Delete EMAIL_BACKEND to print emails in the terminal instead.
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=true
EMAIL_HOST_USER=youraddress@gmail.com
EMAIL_HOST_PASSWORD=your16letterapppassword
DEFAULT_FROM_EMAIL=youraddress@gmail.com

# Where the frontend runs (used in the links inside emails)
FRONTEND_URL=http://localhost:3000
```

Generate a new secret key with:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Tips:

* Put the `SECRET_KEY` in single quotes, because characters like `%`, `$` and `#` can break `.env` parsing.
* `EMAIL_HOST_PASSWORD` is a Gmail **app password**, not your normal password, written without spaces.
* Restart `runserver` (and the Celery worker) after changing `.env`. It is only read at startup.
* Delete `EMAIL_BACKEND`, or leave `AT_API_KEY` empty, to test without real email or SMS. Messages then print in the terminal.

---

##  Running the project

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
python manage.py makemigrations users   # after changing a model
python manage.py migrate                # apply migrations
python manage.py changepassword 0712345678   # change a user's password (use the phone number)
python manage.py shell                  # open a Django shell
```

---

##  How account verification works

Residents must verify their account before they can sign in. Here is the full flow:

```text
1. Resident registers            POST /api/auth/register/
        │                        → account created, unverified
        ▼
2. A 6-digit code is sent        by email and SMS
        │
        ▼
3. Resident confirms the code    POST /api/auth/verify/confirm/
        │                        → account marked verified
        ▼
4. Resident signs in             POST /api/auth/login/
                                 → receives access and refresh tokens
```

Rules of the one-time codes:

* The code is stored **hashed**, never in plain text.
* It expires after **15 minutes**.
* A wrong code can be tried **5 times**, then it is burned and a new one is needed.
* A new code can be requested once every **60 seconds**. Only the newest code works.
* The same mechanism powers **forgot password** and the admin's **send reset** for staff.
* The email also contains a link to the frontend, `/verify?id=...&code=...`, which verifies automatically.

If someone logs in before verifying, the API answers **403** with "Please verify your account first." and the frontend sends them to the verify page.

**After deploying this feature to an existing database**, mark current residents as verified once, or they will be locked out:

```bash
python manage.py shell -c "from django.contrib.auth import get_user_model as g; g().objects.update(is_phone_verified=True)"
```

Staff accounts created by an admin are verified automatically.

---

## 👥 Roles and permissions

| Action | Citizen | Officer (`STAFF`) | Dept head (`DEPT_HEAD`) | Admin (`ADMIN`) |
|---|:--:|:--:|:--:|:--:|
| Register and log in | ✅ | ✅ | ✅ | ✅ |
| Create a service request | ✅ | | | |
| See own requests | ✅ | | | |
| See requests of own department | | ✅ | ✅ | ✅ |
| Change a request's status | ❌ | ✅ | ✅ | ✅ |
| Assign an officer to a request | ❌ | ❌ | ✅ | ✅ |
| Manage staff accounts | ❌ | ❌ | ❌ | ✅ |
| Read the audit log | ❌ | ❌ | ❌ | ✅ |
| Create announcements | ❌ | | | ✅ |

Other rules enforced by the API:

* Nobody can give themselves a role at registration. Anyone who registers is a `CITIZEN`, even if they send `"role": "ADMIN"`.
* Staff cannot be created with the `CITIZEN` role, and a temporary password is required.
* Admins cannot deactivate their own account.
* A deactivated staff member can no longer log in.

---

##  API reference

Base URL (local): `http://127.0.0.1:8000`

Protected endpoints need this header, where the token comes from the login response:

```text
Authorization: Bearer <access_token>
```

### Authentication

| Method | Endpoint | Auth | Purpose |
|---|---|---|---|
| POST | `/api/auth/register/` | None | Create a citizen account and send a verification code |
| POST | `/api/auth/verify/send/` | None | Send (or resend) a verification code |
| POST | `/api/auth/verify/confirm/` | None | Confirm the code and verify the account |
| POST | `/api/auth/login/` | None | Log in with phone or email, returns `access` and `refresh` |
| POST | `/api/auth/refresh/` | None | Exchange a refresh token for a new access token |
| GET | `/api/auth/me/` | Token | Current user's profile |
| POST | `/api/auth/password/forgot/` | None | Send a password reset code |
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

The admin chooses a temporary password, then sends a reset code so the staff member picks their own. The admin never sees the user's real password.

### Other

| Method | Endpoint | Purpose |
|---|---|---|
| GET / POST | `/api/announcements/` | List or create announcements (create is admin only) |
| GET | `/api/audit-logs/` | Audit trail (admin only) |

---

## Testing the API with Postman

A ready-made collection with **88 requests** and automatic tests is in `postman/muranga-ecitizen-api.postman_collection.json`.

### 1. Import it

Postman → **Import** → choose the file. (If the file won't open, use **Import → Raw text** and paste its contents.)

### 2. Set the variables

Open the collection → **Variables** tab and set:

| Variable | Value |
|---|---|
| `baseUrl` | `http://127.0.0.1:8000` (already set) |
| `adminPhone` | Phone number of your County Admin account |
| `adminPassword` | That account's password (never commit this) |

Make sure at least one department and one category exist.

### 3. Run it

Start the backend, then right-click the collection → **Run**. Run the folders from top to bottom. Tokens and IDs are saved automatically between requests.

### 4. Paste the one-time codes

Postman can't read your email or terminal, so three requests need a code that the backend printed in the `runserver` terminal (or emailed):

| Variable | Used by |
|---|---|
| `verifyCode` | "Confirm verification: real code" (citizen A) |
| `verifyCodeB` | "Confirm verification for B" (citizen B) |
| `resetCode` | "Reset with real code" (password reset) |

Copy the **newest** 6-digit code into the variable, then run that request. If you'd rather skip this, mark the test users as verified in the Django shell.

### What the folders check

| Folder | What it tests |
|---|---|
| 0. Health | API is up |
| 1. Reference data | Departments and categories (and saves their IDs) |
| 2. Auth: citizen A | Register, duplicates, blocked login before verifying, verify, every login style, refresh, `me` |
| 3. Service requests | Create, list, open, edit, and that citizens can't resolve requests, list staff or read the audit log |
| 4. Citizen B | Privilege escalation attempt at registration, and that B can't see, edit or delete A's data |
| 5. Admin | Admin login, create officer and department head, validation errors, send reset |
| 6. Officer and head | Status changes, assignment rules, timeline |
| 7. Announcements | Create, update and delete, and citizen restrictions |
| 8. Password recovery | Forgot, reset, change password |
| 9. Cleanup | Deactivate test staff and confirm they can't log in |

### Expected results

| Check | Expected status |
|---|---|
| Register a new citizen | `201` |
| Register the same phone again | `400` |
| Log in before verifying | `403` |
| Wrong verification code | `400` |
| Wrong password at login | `401` |
| `/api/auth/me/` with no token | `401` |
| Citizen opens `/api/staff/` | `403` |
| Citizen B opens citizen A's request | `403` or `404` |
| Officer assigns a request | `403` |
| Invalid status such as `Nonsense` | `400` |
| Admin deactivates staff | `204` |

### Quick manual test without the collection

1. `POST /api/auth/register/` with a phone, username, email and password.
2. Read the 6-digit code in the `runserver` terminal.
3. `POST /api/auth/verify/confirm/` with `identifier` and `code`.
4. `POST /api/auth/login/` and copy the `access` token.
5. `POST /api/requests/` with that token in the `Authorization` header.

> Some announcement fields and the "admin cannot deactivate own account" check depend on your serializers and IDs. Adjust those requests if they fail.

---

##  Email and SMS setup

### Email (Gmail SMTP)

1. Turn on **2-Step Verification** for the Google account.
2. Go to https://myaccount.google.com/apppasswords and create an app password.
3. Put it in `.env` as `EMAIL_HOST_PASSWORD`, without spaces.
4. Restart the server and trigger an email (for example register a new user).

A `535` authentication error means a normal password was used instead of an app password, or 2-Step Verification is off.

### SMS (Africa's Talking)

1. Sign up at https://africastalking.com and open the **Sandbox** app.
2. Go to **Settings → API Key** and generate a key.
3. Put `AT_USERNAME=sandbox` and `AT_API_KEY=<key>` in `.env`.
4. Open the **Simulator** from the dashboard to read the messages.

The **sandbox never sends to real phones**. To reach real residents you need a live Africa's Talking app with credit, and a live username.

While developing without an API key, SMS messages are **printed in the terminal** instead, so you can keep working.

---

##  Deployment on Render

Live API: _link to be added after deployment_

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
| `ALLOWED_HOSTS` | Your Render hostname, for example `your-api.onrender.com` |
| `DATABASE_URL` | Your Neon connection string |
| `AT_USERNAME`, `AT_API_KEY` | Africa's Talking credentials |
| `REDIS_URL` | A hosted Redis URL (only if you use Celery) |
| `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_REFRESH_TOKEN`, `GMAIL_SENDER` | Recommended on Render: Gmail API credentials and the authorized Gmail sender address |
| `BREVO_API_KEY`, `BREVO_SENDER_EMAIL` | Optional HTTPS email-provider fallback |
| `EMAIL_*`, `DEFAULT_FROM_EMAIL` | SMTP fallback settings; Render may restrict outbound SMTP, so prefer an HTTPS provider |
| `FRONTEND_URL` | Your live frontend address (not `localhost`) |

Email delivery is performed before the API request completes so a Render worker
shutdown cannot discard a daemon-thread send. Configure Gmail API or Brevo
credentials in Render rather than relying on Django's console backend; with no
real provider configured, production logs an explicit delivery error instead
of reporting the email as sent.

Also add the live frontend address to your CORS allowed origins in `settings.py`.

### After the first deploy

1. Open the Render **Shell** and create the admin: `python manage.py createsuperuser`.
2. Mark existing residents verified (only needed when upgrading a database that already has users):

```bash
python manage.py shell -c "from django.contrib.auth import get_user_model as g; g().objects.update(is_phone_verified=True)"
```

3. Visit the live address. You should see the `{"status": "ok"}` health check.
4. In Postman, change `baseUrl` to the live address and run the collection again.

---

##  Git workflow

Each piece of work gets its own branch and pull request:

```bash
git checkout main
git pull
git checkout -b feature/backend-account-verification
git add backend
git commit -m "Add one-time-code account verification and password reset"
git push -u origin feature/backend-account-verification
```

Then open a pull request into `main`. Merge the **backend** pull request before the frontend one, because the frontend pages call the new endpoints.

`.env` files, `venv/`, `__pycache__/` and similar are ignored by `backend/.gitignore`.

---

##  Security notes

* **Secrets stay out of Git.** `.env` is ignored. Only `.env.example` is committed, with no real values.
* **If a secret is ever shared or committed,** rotate it: reset the Neon password and generate a new `SECRET_KEY`.
* **One-time codes are hashed**, expire, are single-use and limited to 5 attempts.
* **No account probing.** Forgot-password and send-code answer the same way whether or not the account exists.
* **Passwords** are validated with Django's password rules and stored hashed.
* **Role escalation is blocked.** Roles can't be chosen at registration.
* **Data isolation.** Citizens can only reach their own requests.
* **Accounts are deactivated, not deleted,** so the audit trail stays intact.
* Use **long, unique passwords** for admin accounts and never share them in chat or screenshots.

---

##  Troubleshooting

| Problem | Likely cause and fix |
|---|---|
| Verify page stays stuck, `400` in the terminal | Wrong, expired or replaced code. Use the **newest** code, enter all 6 digits (it can start with 0), or press **Resend code** and wait 60 seconds. |
| Login returns `403` | The account isn't verified. Verify it, or mark it verified in the Django shell. |
| Login returns `401` | Wrong credentials, or the staff account was deactivated. |
| Existing users locked out after the update | Run the "mark all users verified" command from the verification section. |
| `SMTPAuthenticationError 535` | Use a Gmail app password with 2-Step Verification, no spaces. |
| Emails print in the terminal | `EMAIL_BACKEND` is missing, which is the intended test mode. Set the SMTP backend to send for real. |
| `SSL: WRONG_VERSION_NUMBER` when sending SMS | A proxy, VPN or antivirus is interfering. Clear `HTTPS_PROXY` and `HTTP_PROXY`, or leave `AT_API_KEY` empty to print SMS in the terminal. |
| SMS not arriving on a phone | The Africa's Talking sandbox only logs messages in the simulator. |
| Africa's Talking `401` | Sandbox keys only work with the username `sandbox`. Check for stray spaces in the key. |
| `No installed app with label 'users'` | Check the app's `name` and `label` in `apps/users/apps.py`. |
| Celery can't connect | Redis isn't running, or `REDIS_URL` is wrong. Use `--pool=solo` on Windows. |
| Browser shows a CORS error | Add the frontend address (`http://localhost:3000`) to the CORS allowed origins. |
| Changes in `.env` ignored | Restart `runserver` and the Celery worker. |

---

##  How the backend was built

1. **Project and apps.** A Django project (`config`) with modular apps: `users`, `categories`, `service_requests`, `announcements`, `notifications`, `audit_logs`.
2. **Custom user model.** `User` extends `AbstractUser` with a `role`, a unique `phone_number` (used as the login field), `home_ward`, `sub_county`, `is_phone_verified` and a `department`. A case-insensitive unique constraint allows only one account per email address.
3. **JWT authentication.** Login and refresh endpoints using `djangorestframework-simplejwt`.
4. **Flexible login.** A custom serializer accepts a phone number or an email as `identifier`, normalises `+254...` phone numbers, and keeps the older `phone_number` field working.
5. **Reference data.** Departments and categories exposed as read-only lists.
6. **Service requests.** Create, list and detail with reference numbers, a `Pending` starting status, a timeline, status changes and officer assignment. Citizens only see their own requests.
7. **Staff management.** Admin-only API to create, update and deactivate staff, with role validation and an audit mixin.
8. **Audit logs.** An append-only record of actions, readable only by admins.
9. **Announcements** for county notices.
10. **One-time codes.** A `OneTimeCode` model plus `otp.py` and `verification.py` for account verification, forgot password, reset and change password, with hashed codes, expiry, attempt limits and a resend cooldown.
11. **Delivery.** Codes go out by email (Gmail SMTP) and SMS (Africa's Talking), with a terminal fallback for development.
12. **Login protection.** Unverified citizens are blocked at login with a clear message.
13. **Testing.** A PowerShell smoke-test script and the Postman collection that cover public, citizen, privacy, officer, head and admin behaviour.
14. **Repository hygiene.** A backend `.gitignore`, a `.env.example` template, feature branches and pull requests.
15. **Deployment.** Gunicorn and WhiteNoise on Render with Neon PostgreSQL.

---

##  License and contact

Built for Murang'a County as a digital public service project. Add your license and contact details here.
kbwaceke@gmail.com
0112280703