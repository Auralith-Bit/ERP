# AURALITH ERP

**Enterprise Resource Planning** system for **Auralith Bit** — a training and development organization. Manages courses, mentors, students, employees, departments, projects, budgeting, ID cards, certificates, and notifications.

Built with Django 4.2+.

---

## Quick Start

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Browse to **http://localhost:8000**

### Production Build (Render)

A `build.sh` script is included for Render's build step:

```bash
./build.sh   # pip install → collectstatic → migrate
```

Set the following environment variables in your Render dashboard:

| Variable | Required | Notes |
|----------|----------|-------|
| `SECRET_KEY` | Yes | Long random string |
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `ALLOWED_HOSTS` | Yes | Comma-separated (e.g. `myapp.onrender.com,localhost`) |
| `DEBUG` | No | Set to `True` for local dev only |
| `EMAIL_HOST_USER` | No | Gmail address for payment receipts |
| `EMAIL_HOST_PASSWORD` | No | Gmail app password |
| `STAFF_REGISTRATION_CODE` | No | Defaults to `AURALITH2024` |

### Email Setup

Payment receipts are sent through Gmail SMTP. Set these environment variables before running the server:

```bash
EMAIL_HOST_USER=your-main-gmail@gmail.com
EMAIL_HOST_PASSWORD=your-gmail-app-password
```

For Gmail, use an **App Password** instead of your normal Gmail password.

> Credentials default to empty in `settings.py`. Never commit real credentials — set them via environment variables only.

### Default Credentials

| Username | Password | Role |
|----------|----------|------|
| `admin` | `admin123` | Superuser (full access) |
| `staff` | `staff123` | Staff (limited access) |

---

## Features

### Authentication & Validation
- **Login form** — client-side validation (non-empty fields, min password length) with inline error messages, server-side validation fallback
- **Register form** — client-side validation (username/email required, email format, password min 8 chars, password confirmation match), form data persists on validation errors
- **Staff register** — same validation improvements with password length check
- **Username validation** — username must not start with a digit (enforced both client-side and server-side across all registration and login forms)
- Error messages displayed on the same page without losing form data

### Course Management
- Course catalog with mentor assignments, category color-coding, enrollment tracking
- Syllabus file upload and download per course
- Progress tracking with completion percentage per course
- **My Courses page** — shows "No Enrolled Courses" message with info alert when a student has no course enrollments (instead of a generic redirect)

### People Management
- **Students** — self-registration, enrollment in courses, intern promotion. New student registrations automatically assigned to the `student` auth Group.
- **Mentors** — profile cards with specialization, bio, and course count
- **Employees** — filterable table by type (Intern/Staff/Mentor/Admin), department assignment
- **Departments** — organizational structure with head and member lists

### Certification System
- Three certificate types: **Course**, **Workshop**, **Internship**
- Auto-issuance when a course enrollment is marked "completed"
- Manual issuance via staff form with configurable signer, title, location, dates
- **HTML preview** — styled certificate with gold borders, gradient backgrounds, watermarks
- **PDF download** — generates letter-size PDF using **Playwright** (Chromium), identical to preview
- Auto-regeneration: cached PDF deleted when certificate data changes
- Force-regenerate via `?force=1` query parameter
- Revoke/reissue actions in admin panel

### ID Card System
- Generate student and employee ID cards
- QR code encoding (student info or employee info) embedded in each card
- Upload ID card images for students/employees
- Image viewer modal and delete support
- QR verification endpoint

### Financial Dashboard
- Budget & fees page with fee structure table (client-side localStorage CRUD)
- Revenue, pending, collected KPIs
- Project budget allocation with progress bars

### Notification System
- Admin-created notifications displayed to all users
- Bell icon with unread count badge in navigation bar
- Polls `/api/notifications/` every 15 seconds via `fetch()`
- Seen/unseen tracking using `localStorage`

### Global Search
- Searches across Courses, Mentors, Students, Projects, Employees, and Departments
- Results grouped by entity type on a dedicated search results page

### Database Workbench
- Browse all `erp_app` models with field listing and record counts
- Dynamic table view for any model with sortable columns
- Number input spinners (increase/decrease arrows) and scroll-wheel value changes removed globally via CSS and JS — applies to all number/decimal fields including `total_fee` (CourseEnrollment), `amount` (Payment), and all Admin forms

### System Integration
- Integration page with service connection cards (Google, Slack, Payment Gateway, Mailchimp, Cloud, Analytics)
- Placeholder UI ready for API connections

### Dark Mode
- Light/dark theme toggle persisted in `localStorage`
- Admin interface also themed via custom CSS/JS

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Framework | Django >=4.2, <5.3 |
| Database | PostgreSQL (production) / SQLite (development) |
| WSGI Server | Gunicorn |
| Static Files | WhiteNoise |
| QR Codes | `qrcode[pil]` >=7.0 |
| Icons | Phosphor Icons (CDN) |
| CSS | Custom variables with light/dark themes |
| JS | Vanilla JS (no frameworks) |

---

## Architecture

```
AURALITH erp/
│
├── build.sh                  # Render build script (install → collectstatic → migrate)
│
├── auralith_erp/              # Django project config
│   ├── settings.py            # All configuration (DB, auth, static, media)
│   ├── urls.py                # Root URL dispatcher
│   └── wsgi.py / asgi.py      # WSGI/ASGI entry points
│
├── erp_app/                   # Main application
│   ├── models.py              # 9 models (340 lines)
│   ├── views.py               # 25+ view functions (1031 lines)
│   ├── urls.py                # 31 URL patterns
│   ├── admin.py               # Admin registrations for all models
│   ├── roles.py               # RBAC: constants, decorators, helpers
│   ├── signals.py             # Auto-group assignment, auto-certificates
│   ├── context_processors.py  # Sidebar stats + user globals
│   ├── templatetags/
│   │   └── erp_extras.py      # Custom template filter (get_attr)
│   │
│   ├── templates/
│   │   ├── admin/             # Admin overrides (theme, login)
│   │   └── erp_app/           # 24 application templates
│   │
│   └── static/
│       └── erp_app/
│           ├── css/style.css      # All app styles (405 lines)
│           ├── css/admin-theme.css # Admin dark mode
│           └── js/admin-theme.js   # Admin toggle button
│
├── media/                     # User-uploaded files
│   ├── certificates/          # Generated PDF certificate files
│   ├── id_cards/              # Uploaded ID card images
│   └── syllabi/               # Uploaded course syllabi
│
├── staticfiles/               # Collected static assets (collectstatic)
│
└── db.sqlite3                 # Development database
```

---

## Database Models (9 total)

### Mentor
| Field | Type | Notes |
|-------|------|-------|
| `name` | CharField(200) | |
| `email` | EmailField | unique |
| `specialization` | CharField(200) | |
| `bio` | TextField | blank |

### Department
| Field | Type | Notes |
|-------|------|-------|
| `name` | CharField(200) | unique |
| `description` | TextField | blank |

### Course
| Field | Type | Notes |
|-------|------|-------|
| `name` | CharField(200) | |
| `mentor` | ForeignKey(Mentor) | null, on_delete=SET_NULL |
| `category` | CharField(50) | development, design, qa, marketing |
| `duration_weeks` | PositiveIntegerField | default=8 |
| `status` | CharField(20) | live, upcoming, enrollment, completed |
| `syllabus` | FileField | uploads to syllabi/ |
| `students_count` | PositiveIntegerField | default=0 |
| `completion_percent` | PositiveIntegerField | default=0 |

### Student
| Field | Type | Notes |
|-------|------|-------|
| `user` | OneToOneField(User) | null, related_name='student_profile' |
| `name` | CharField(200) | |
| `email` | EmailField | unique |
| `phone` | CharField(20) | blank |
| `is_intern` | BooleanField | default=False |

### CourseEnrollment
| Field | Type | Notes |
|-------|------|-------|
| `student` | ForeignKey(Student) | |
| `course` | ForeignKey(Course) | |
| `status` | CharField(20) | active, completed, dropped |
| **Meta:** | `unique_together` | (student, course) |

**Signal:** When status → `completed`, auto-creates a Certificate.

### Certificate
| Field | Type | Notes |
|-------|------|-------|
| `student` | ForeignKey(Student) | |
| `course` | ForeignKey(Course) | nullable |
| `certificate_type` | CharField(20) | course, internship, workshop |
| `certificate_number` | CharField(50) | auto: `CERT-YYYY-XXXX` |
| `issue_date` | DateField | auto_now_add |
| `status` | CharField(20) | issued, pending, revoked |
| `file` | FileField | cached PDF path |
| `program_title` | CharField(255) | overrides course name on cert |
| `program_start_date` | CharField(40) | display value |
| `location` | CharField(150) | default "Auralith Bit" |
| `internship_details` | TextField | body text for internship type |
| `authorized_signer_name` | CharField(150) | default "Supriya Dwivedi" |
| `authorized_signer_title` | CharField(150) | default "Full Stack Developer" |
| `authorized_signature_text` | CharField(150) | cursive signature override |

**Properties:** `certificate_heading`, `completion_sentence`, `certificate_body`, `dynamic_signature`, `ceo_founder_name`, `ceo_founder_title` — content adapts to certificate type.

**Save behavior:** Auto-deletes cached PDF when tracked fields change.

### IDCard
| Field | Type | Notes |
|-------|------|-------|
| `card_type` | CharField(20) | student, employee |
| `student` | ForeignKey(Student) | nullable |
| `employee` | ForeignKey(Employee) | nullable |
| `file` | FileField | uploads to id_cards/ |

### Employee
| Field | Type | Notes |
|-------|------|-------|
| `name` | CharField(200) | |
| `email` | EmailField | unique |
| `department` | ForeignKey(Department) | nullable |
| `role` | CharField(200) | free text |
| `employee_type` | CharField(20) | intern, staff, mentor, admin |

### Notification
| Field | Type | Notes |
|-------|------|-------|
| `title` | CharField(200) | |
| `message` | TextField | |
| `created_by` | ForeignKey(User) | nullable |
| `is_active` | BooleanField | default=True |

### Project
| Field | Type | Notes |
|-------|------|-------|
| `name` | CharField(200) | |
| `description` | TextField | blank |
| `client` | CharField(200) | blank |
| `status` | CharField(20) | in_progress, completed, on_hold, cancelled |
| `progress_percentage` | PositiveIntegerField | default=0 |
| `budget` | DecimalField(10,2) | default=0 |

---

## User Roles & Permissions

| Role | Auth Group | Determined By |
|------|-----------|---------------|
| **Super Admin** | `super_admin` | `user.is_superuser` |
| **Teaching Staff** | `teaching_staff` | `user.groups` membership |
| **Normal Staff** | `normal_staff` | `user.groups` membership |
| **Student** | `student` | Existence of `user.student_profile` |
| **Intern** | `intern` | `is_intern=True` on Student profile |

### Permission Matrix

| Resource | Super Admin | Teaching Staff | Normal Staff | Student | Intern |
|----------|:-----------:|:--------------:|:------------:|:-------:|:------:|
| Course | CRUD | CRUD | View | View | View |
| Mentor | CRUD | CRUD | View | View | View |
| Student | CRUD | CRUD | View | — | — |
| Certificate | CRUD + issue | CRUD + issue | View | View | View |
| Employee | CRUD | View | CRUD | — | View |
| Department | CRUD | View | CRUD | — | View |
| IDCard | CRUD | — | CRUD | — | — |
| Project | CRUD | — | CRUD | — | — |
| Notification | CRUD | Add/View | Add/View | — | — |

### Decorators (in `erp_app/roles.py`)

| Decorator | Allowed Roles |
|-----------|--------------|
| `@role_required(SUPER_ADMIN, TEACHING_STAFF)` | super_admin, teaching_staff |
| `@teaching_staff_required` | super_admin, teaching_staff |
| `@normal_staff_required` | super_admin, normal_staff, teaching_staff |
| `@staff_required` | super_admin, teaching_staff, normal_staff |

---

## URL Routes

### Authentication (no login required)
| Route | View | Description |
|-------|------|-------------|
| `/` | `index` | Redirect to dashboard or login |
| `/login/` | `login_view` | Login form (GET/POST) |
| `/logout/` | `logout_view` | Logout and redirect |
| `/register/` | `register_view` | Student self-registration |
| `/register/staff/` | `staff_register_view` | Staff registration (code-gated) |
| `/password-reset/` | `password_reset` | Password reset form (UI-only) |

### Main Pages
| Route | View | Description |
|-------|------|-------------|
| `/dashboard/` | `dashboard` | KPI stats, courses table, projects |
| `/courses/` | `courses` | Course card grid |
| `/courses/&lt;id&gt;/syllabus/` | `course_syllabus` | Syllabus view/download |
| `/mentors/` | `mentors` | Mentor profile cards |
| `/employees/` | `employees` | Filterable employee table |
| `/departments/` | `departments` | Department cards |
| `/integration/` | `integration` | Service connection cards |

### Certificates
| Route | View | Description |
|-------|------|-------------|
| `/certificates/` | `certificates` | Certificate list with filters |
| `/certificates/issue/` | `issue_certificate` | Manual certificate issuance |
| `/certificates/&lt;id&gt;/` | `preview_certificate` | Styled HTML preview |
| `/certificates/&lt;id&gt;/download/` | `download_certificate` | PDF download (Playwright) |

### ID Cards
| Route | View | Description |
|-------|------|-------------|
| `/id-generation/` | `id_generation` | Upload ID card images |
| `/api/generate-student-id/` | `generate_student_id` | Generate student ID with QR |
| `/api/generate-employee-id/` | `generate_employee_id` | Generate employee ID with QR |
| `/api/verify-id-card/` | `verify_id_card` | Verify QR code data |
| `/api/delete-id-card/&lt;id&gt;/` | `delete_id_card` | Delete an ID card |

### API Endpoints
| Route | View | Returns |
|-------|------|---------|
| `/api/get-students/` | `get_students` | JSON list |
| `/api/get-employees/` | `get_employees` | JSON list |
| `/api/get-courses/` | `get_courses` | JSON list |
| `/api/get-departments/` | `get_departments` | JSON list |
| `/api/notifications/` | `notifications_feed` | JSON array (active) |

### Utilities
| Route | View | Description |
|-------|------|-------------|
| `/search/` | `search` | Global search across 6 entities |
| `/workbench/` | `workbench` | Database model overview |
| `/workbench/&lt;app&gt;/&lt;model&gt;/` | `workbench_table` | Dynamic table browser |
| `/budget-fees/` | `budget_fees` | Fee management dashboard |
| `/promote-intern/&lt;student_id&gt;/` | `promote_to_intern` | Promote student to intern |

---

## Certificate PDF Generation

The certificate download pipeline uses **Playwright** (headless Chromium), not WeasyPrint:

1. **Template:** `certificate_download.html` renders the certificate with `is_pdf=True`
2. **Static files:** `/static/` paths are rewritten to `file://` absolute paths so Chromium can load them offline
3. **Playwright:** Launches headless Chromium, sets the HTML content, generates a PDF via `page.pdf()`
4. **Page format:** Letter size (8.5" × 11"), portrait, zero margins, `print_background=True`
5. **Caching:** Generated PDF saved to `media/certificates/` and cached on the model's `file` field
6. **Auto-invalidation:** When certificate data changes (student, title, signer, etc.), the cached PDF is deleted on `save()`
7. **Force regenerate:** Visit `/certificates/<id>/download/?force=1` to bypass cache

**Fonts:** Render exactly as in the browser (same Chromium engine) — Brush Script MT, Segoe UI, Georgia, etc.

---

## Signals

| Signal | Trigger | Action |
|--------|---------|--------|
| `assign_user_groups` | Student post_save | Auto-assigns `student` (and `intern`) auth Groups to linked User |
| `auto_create_course_certificate` | CourseEnrollment post_save | Auto-creates Certificate when enrollment → `completed` |

Additionally, the `register_view` directly assigns the `student` group to newly registered users for redundancy.

---

## Admin Interface

All 9 models registered in `admin.py` with `list_display`, `list_filter`, `search_fields`:

- **CourseEnrollmentInline** on Course admin
- **CertificateAdmin** — `fieldsets` grouping, custom actions (revoke, reissue), search by number/student
- Admin login page overridden with password show/hide toggle
- Admin base overridden with dark mode toggle

---

## Context Processor

`erp_app.context_processors.sidebar_stats` — available in ALL templates:

- `user_initials` — first letters of user's full name
- `sidebar_employee_count`, `sidebar_department_count`, `sidebar_mentor_count`, `sidebar_student_count`, `sidebar_certificate_count` — navigation badge counts
- `is_super_admin`, `is_teaching_staff`, `is_normal_staff`, `is_student`, `is_intern`, `is_any_staff` — role booleans for template conditional rendering

---

## Dependencies

```
Django>=4.2,<5.3        # Web framework
gunicorn                # WSGI HTTP server (production)
whitenoise              # Static file serving (production)
psycopg2-binary         # PostgreSQL adapter (production)
dj-database-url         # Parse DATABASE_URL into Django config
qrcode[pil]>=7.0        # QR code generation (with Pillow)
```

---

## Creating a Superuser

```bash
python manage.py createsuperuser
```

Then visit `/admin/` to manage all models.

---

## Staff Registration Code

Set via the `STAFF_REGISTRATION_CODE` environment variable (defaults to `AURALITH2024` in `settings.py`).

Required when registering a new staff account at `/register/staff/`.
