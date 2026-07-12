# City of Mutare Digital ID System (MCC Digital ID)

A facial-recognition-based physical access control and visitor management system built for the **City of Mutare Municipal Council (MCC)** in Zimbabwe. The system enables employee enrollment via webcam, real-time face verification at municipal centres, visit logging, gadget tracking, manual override workflows, and an AI-powered chatbot for querying system data.

---

## Table of Contents

- [Features](#features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Default Accounts](#default-accounts)
- [Seeded Data](#seeded-data)

---

## Features

- **Employee Enrollment** -- Webcam-based capture with 128-dimensional face encoding storage
- **Face Verification** -- Real-time face matching against enrolled employees using Euclidean distance (tolerance 0.5)
- **Visit Logging** -- Timestamped visitor logs with purpose, site name, and notes
- **Gadget Check-in/Check-out** -- Track laptops, phones, tablets, hard drives, and cameras per visit
- **Manual Override** -- Fallback verification workflow when face recognition fails
- **AI Chatbot** -- LLaMA 3.3 70B-powered assistant with 9 real-time database tools for querying stats, employees, logs, and attendance
- **Dashboards** -- Live-updating admin and staff dashboards with Chart.js visit trends
- **Reports & CSV Export** -- Employee attendance reports with downloadable CSV
- **Role-Based Access** -- Admin (full access) and Site Staff (centre-scoped) roles
- **Multi-Centre Support** -- 7 municipal centres with isolated staff access

---

## Tech Stack

### Languages

| Language | Version | Purpose |
|----------|---------|---------|
| Python | 3.13 | Backend logic, database, face recognition, AI chatbot |
| JavaScript | ES6+ | Frontend interactivity (webcam, chatbot, real-time polling) |
| HTML | Jinja2 | Server-rendered templates (17 pages) |
| CSS | 3 | Custom styling (1410 lines) |
| SQL | -- | SQLite database schema and queries |

### Backend

| Tool/Library | Version | Purpose |
|--------------|---------|---------|
| Flask | -- | Web framework (routes, sessions, templating, JSON API) |
| SQLite | -- | Primary database engine |
| Werkzeug | -- | Password hashing (bundled with Flask) |
| face_recognition | -- | Face detection and encoding (dlib-based) |
| dlib-bin | -- | Pre-compiled dlib binary for face_recognition |
| openai | -- | OpenAI-compatible client for Groq/OpenRouter AI APIs |
| python-dotenv | -- | Environment variable loading from `.env` |
| Gunicorn | -- | WSGI HTTP server for production |

### Frontend

| Library | Version | Purpose |
|---------|---------|---------|
| Bootstrap | 5.3.3 | CSS framework and responsive grid |
| Bootstrap Icons | 1.11.3 | Icon font (200+ icons) |
| Chart.js | 4.4.7 | Visit trends line chart on admin dashboard |
| Inter (Google Font) | 500/600/700 | Typography |

### AI / External Services

| Service | Details |
|---------|---------|
| Groq API | AI inference endpoint (`llama-3.3-70b-versatile` model) |
| OpenRouter | Fallback AI endpoint |
| Neon Database | PostgreSQL connection (available but not currently in use) |

### DevOps & Tools

| Tool | Purpose |
|------|---------|
| Git | Version control |
| Python venv | Virtual environment |
| pip | Python package manager |
| ngrok | HTTPS tunneling for local development |
| Self-signed SSL certs | Local HTTPS via `certs/cert.pem` and `certs/key.pem` |

---

## Project Structure

```
CityOfMutareDigitaliD/
|-- app.py                      # Main Flask application (entry point)
|-- database.py                 # SQLite database layer and migrations
|-- face_utils.py               # Face encoding and matching utilities
|-- chatbot.py                  # AI chatbot with OpenAI-compatible function calling
|-- evaluate.py                 # Face recognition accuracy evaluation CLI tool
|-- requirements.txt            # Python dependencies
|-- .env                        # Environment variables (API keys, config)
|-- loginbg.png                 # Login background image
|-- mutarelogo.png              # City of Mutare logo
|
|-- instance/
|   |-- database.db             # SQLite database file
|
|-- certs/
|   |-- cert.pem                # SSL certificate
|   |-- key.pem                 # SSL private key
|
|-- static/
|   |-- css/style.css           # Custom stylesheet
|   |-- js/camera.js            # Webcam capture and switching
|   |-- js/chat.js              # Chatbot widget UI
|   |-- enrolled_photos/        # Enrolled employee face photos
|   |-- unrecognized_photos/    # Captured unrecognized face photos
|
|-- templates/
|   |-- base.html               # Base layout (header, sidebar, chatbot)
|   |-- welcome.html            # Landing page
|   |-- login.html              # Login form
|   |-- verify.html             # Admin face verification
|   |-- admin_dashboard.html    # Admin dashboard with stats and charts
|   |-- staff_dashboard.html    # Staff dashboard (centre-specific)
|   |-- admin/                  # Admin pages (10 templates)
|   |-- staff/                  # Staff pages (2 templates)
```

---

## Installation

```bash
# Clone the repository
git clone https://github.com/geniuskudzai21/CityOfMutareDigitaliD.git
cd CityOfMutareDigitaliD

# Create and activate virtual environment
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

---

## Configuration

Create a `.env` file in the project root with the following variables:

```env
GROQ_API_KEY=your_groq_api_key
OPENROUTER_API_KEY=your_openrouter_api_key
AI_MODEL=llama-3.3-70b-versatile
AI_BASE_URL=https://api.groq.com/openai/v1
```


## Usage

```bash
# Run the development server
python app.py

# Or with Gunicorn (production)
gunicorn app:app
```

The application will be available at `https://localhost:5000` (HTTPS with self-signed cert).

### Municipal Centres (7)

Civic Centre, Stores, Moffat, Chikanga, Hobhouse, Odzani, FernValley

### Departments (18)

ICT, HR, Traffic, Finance, Debtors, Payments, Salaries, Security, Spatial Planning, GIS, Engineering, Health, Housing, Procurement, Accountant Expenditure, Audit, Cashier, Assets
