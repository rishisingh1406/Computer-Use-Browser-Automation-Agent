# Computer-Use Browser Agent

An autonomous browser automation agent built with **Python, Playwright, Groq, Pydantic, and vision-assisted grounding**.

The agent can navigate real websites, perceive page state, choose browser actions, recover from failed actions, extract structured pricing information, and execute secure login workflows without exposing credentials to the LLM.

## Features

* Autonomous browser interaction with Playwright
* Perception → Action → Observation loop
* LLM-driven browser action selection
* Vision-assisted element grounding
* DOM-first interaction with visual fallback
* Automatic retry and self-correction after failed actions
* Site-specific planning
* Structured pricing extraction
* Pydantic-based extraction schema validation
* Secure login handling
* Credential isolation from the LLM
* Domain allowlist guardrails
* Confirmation gates for protected actions
* PostgreSQL persistence support
* Dockerized Playwright/Chromium environment
* Comprehensive automated test suite

---

## Architecture

```text
                         ┌──────────────────────┐
                         │      User Goal        │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │   PerSitePlanner     │
                         │                      │
                         │ Goal → BrowserPlan   │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │      PlanRunner      │
                         └──────────┬───────────┘
                                    │
                                    ▼
                  ┌─────────────────────────────────┐
                  │         BrowserAgent            │
                  │                                 │
                  │   Perception → LLM → Action    │
                  └───────────────┬─────────────────┘
                                  │
                     ┌────────────┼────────────┐
                     │            │            │
                     ▼            ▼            ▼
                Screenshot      DOM        Page State
                     │            │            │
                     └────────────┼────────────┘
                                  │
                                  ▼
                         ┌──────────────────────┐
                         │    Groq Browser LLM │
                         │                      │
                         │ BrowserAction JSON   │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │    ActionExecutor    │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │     BrowserTools     │
                         │                      │
                         │ navigate / click     │
                         │ type / scroll        │
                         │ read / screenshot    │
                         └──────────┬───────────┘
                                    │
                                    ▼
                              Playwright
                                    │
                                    ▼
                              Real Browser


                 Failed Action
                      │
                      ▼
              Re-perceive Page
                      │
                      ▼
              Generate New Action
                      │
                      ▼
              Retry / Alternate Path
```

The important design principle is that the LLM **proposes actions**, while deterministic application code controls execution, validation, retries, extraction, and security boundaries.

---

## Project Structure

```text
computer-use-browser-agent/
│
├── app/
│   ├── agent/
│   │   ├── executor.py
│   │   ├── grounding.py
│   │   ├── llm.py
│   │   ├── login.py
│   │   ├── loop.py
│   │   ├── models.py
│   │   ├── perception.py
│   │   ├── planner.py
│   │   └── plan_runner.py
│   │
│   ├── auth/
│   │   ├── credentials.py
│   │   ├── handler.py
│   │   ├── login.py
│   │   ├── redaction.py
│   │   └── sites.py
│   │
│   ├── browser/
│   │   ├── demo.py
│   │   ├── manager.py
│   │   └── tools.py
│   │
│   ├── config/
│   │   └── sites.py
│   │
│   ├── database/
│   │   ├── connection.py
│   │   ├── models.py
│   │   └── repository.py
│   │
│   ├── extraction/
│   │   ├── pricing.py
│   │   └── schemas.py
│   │
│   ├── guardrails/
│   │   └── policies.py
│   │
│   ├── security/
│   │   ├── config.py
│   │   └── guardrails.py
│   │
│   ├── sites/
│   │   └── github.py
│   │
│   └── workflows/
│       └── pricing.py
│
├── tests/
│   ├── test_browser_tools.py
│   ├── test_database.py
│   ├── test_e2e.py
│   ├── test_extraction.py
│   ├── test_grounding.py
│   ├── test_guardrails.py
│   ├── test_perception_loop.py
│   ├── test_plan_runner.py
│   ├── test_planner.py
│   ├── test_pricing_extraction.py
│   ├── test_pricing_workflow.py
│   ├── test_real_llm.py
│   ├── test_real_planner.py
│   ├── test_secure_login.py
│   ├── test_self_correction.py
│   └── test_visual_click.py
│
├── screenshots/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── pytest.ini
└── README.md
```

---

# How It Works

## 1. Planning

A high-level objective is converted into a structured browser plan.

Example:

```text
Goal:
Extract GitHub Copilot pricing.

Plan:

1. Navigate to pricing page
2. Search/find the relevant pricing section
3. Extract visible pricing information
```

The planner produces structured `BrowserPlan` and `PlanStep` objects.

---

## 2. Perception

The agent observes the current browser state.

The perception layer can collect information such as:

* Current URL
* Page title
* Visible text
* Screenshot
* Browser state

This state is provided to the decision layer.

---

## 3. LLM Decision

The browser LLM receives the current observation and determines the next action.

Actions are represented using structured Pydantic models rather than arbitrary text.

Conceptually:

```json
{
  "action": "click",
  "target": "Pricing",
  "description": "Open the pricing page"
}
```

The structured output makes the LLM easier to validate and execute safely.

---

## 4. Action Execution

The executor translates the validated action into deterministic browser operations.

Supported browser operations include:

```text
navigate
click
type_text
read_text
screenshot
scroll
```

Playwright performs the actual browser interaction.

---

# Vision-Assisted Grounding

Websites frequently change their DOM structure.

A selector that worked yesterday may not work today.

This project therefore uses a **DOM-first, vision-assisted fallback strategy**.

```text
                Target Element
                     │
                     ▼
              Try DOM / Selector
                     │
              ┌──────┴──────┐
              │             │
           Success        Failure
              │             │
              ▼             ▼
           Execute     Screenshot
                            │
                            ▼
                     Vision Grounding
                            │
                            ▼
                     Locate Target
                            │
                            ▼
                         Execute
```

The visual grounding system uses a grid-based approach to identify regions of the screenshot before converting the result into an actionable browser target.

This provides a fallback when traditional selectors are unreliable.

---

# Self-Correction

Browser automation is inherently uncertain.

Selectors can fail, pages can change, and the browser may be in a different state than expected.

Instead of immediately failing the entire task, the agent can recover:

```text
Action
  │
  ▼
Execute
  │
  ├── Success ──────────────► Continue
  │
  └── Failure
        │
        ▼
   Re-perceive page
        │
        ▼
   Provide failure feedback
        │
        ▼
   Generate alternative action
        │
        ▼
      Retry
```

The retry system also prevents blindly repeating the same failed action.

Tests verify:

* Recovery after failed actions
* Retry limits
* Alternative actions
* Prevention of repeated failed actions

---

# Structured Pricing Extraction

The browser agent is not responsible for deciding what constitutes valid final pricing data.

Instead, extracted page text is passed to a deterministic pricing extractor.

The output is normalized into:

```text
PricingTable
    │
    ├── site
    ├── product
    ├── currency
    │
    └── plans[]
          ├── name
          ├── price
          ├── currency
          ├── billing_period
          └── description
```

Example:

```json
{
  "site": "github.com",
  "product": "GitHub Copilot",
  "currency": "USD",
  "plans": [
    {
      "name": "Free",
      "price": 0,
      "currency": "USD",
      "billing_period": null
    },
    {
      "name": "Pro",
      "price": 10,
      "currency": "USD",
      "billing_period": "month"
    }
  ]
}
```

Supported currencies include:

```text
USD
EUR
GBP
INR
```

Supported billing periods include:

```text
day
week
month
year
```

The schema validates:

* Required fields
* Empty names
* Negative prices
* Supported currencies
* Supported billing periods
* Multiple plans
* Serialization and JSON round trips

---

# Secure Login

Authentication is isolated from the LLM.

The architecture separates:

```text
LLM
 │
 │ requests authentication
 ▼
Secure Login Layer
 │
 │ retrieves credentials
 ▼
Credential Provider
 │
 │
 ▼
Browser
```

Credentials are loaded from the runtime environment and are not intentionally passed into the LLM context.

The authentication layer also includes secret redaction and validation.

Tests verify that sensitive credential values are not returned through the normal agent flow.

---

# Security Guardrails

The browser agent includes domain-level security controls.

The domain guard validates:

* Allowed domains
* Subdomains
* URL schemes
* Ports
* Username/password URL injection
* Similar-domain attacks
* Prefix/suffix domain attacks
* Unsafe schemes such as `javascript:`, `data:`, and `file:`

Example:

```text
Allowed:

https://github.com
https://www.github.com
https://docs.github.com

Rejected:

https://github.com.attacker.com
https://attacker-github.com
javascript:...
file:///...
```

This provides a deterministic security boundary around browser navigation.

---

# Database

The project includes database support through:

* SQLAlchemy
* PostgreSQL
* Repository abstractions

The Docker Compose configuration provides a PostgreSQL service:

```yaml
services:
  postgres:
    image: postgres:16
```

Database tests verify connectivity and table creation.

---

# Docker

The project includes a Dockerized Playwright environment.

The image contains:

* Python 3.12
* Project dependencies
* Playwright
* Chromium
* Required Chromium system libraries

Build the image:

```bash
docker build -t browser-agent:v1 .
```

Run the container:

```bash
docker run --rm --env-file .env -e BROWSER_HEADLESS=true browser-agent:v1
```

The container runs the browser in headless mode.

A successful smoke test produces output similar to:

```text
--- NAVIGATE ---
{'action': 'navigate',
 'url': 'https://example.com/',
 'title': 'Example Domain',
 'status': 200}

--- READ TEXT ---
Example Domain

--- SCREENSHOT ---
{'action': 'screenshot',
 'path': 'screenshots/example.png',
 ...}
```

---

# Docker Compose

Start the PostgreSQL service with:

```bash
docker compose up -d
```

Check running services:

```bash
docker compose ps
```

Stop the services:

```bash
docker compose down
```

---

# Environment Variables

Create a `.env` file based on `.env.example`.

Example:

```env
GROQ_API_KEY=your_api_key_here
BROWSER_HEADLESS=true
```

Never commit real credentials to Git.

The `.env` file should remain local.

---

# Installation

## Requirements

* Python 3.12+
* Playwright
* Chromium
* Docker Desktop (optional)
* Groq API key for real LLM execution

## Local Setup

Clone the repository:

```bash
git clone <your-repository-url>
cd computer-use-browser-agent
```

Create a virtual environment:

```bash
python -m venv .venv
```

Activate it on Windows:

```powershell
.venv\Scripts\Activate.ps1
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Install Chromium:

```bash
playwright install chromium
```

Create your environment file:

```powershell
Copy-Item .env.example .env
```

Add your API credentials to `.env`.

---

# Running the Demo

Run the local browser demo:

```bash
python -m app.browser.demo
```

For Docker:

```bash
docker build -t browser-agent:v1 .
docker run --rm --env-file .env -e BROWSER_HEADLESS=true browser-agent:v1
```

The demo navigates to `example.com`, reads the page, and captures a screenshot.

---

# Testing

The project uses `pytest`.

Run the complete suite:

```bash
pytest -x -vv
```

Run extraction schema tests:

```bash
pytest tests/test_extraction.py -vv
```

Run pricing extraction tests:

```bash
pytest tests/test_pricing_extraction.py -vv
```

Run self-correction tests:

```bash
pytest tests/test_self_correction.py -vv
```

The current test suite contains **117 tests**, covering:

* Browser tools
* Database
* End-to-end execution
* Extraction schemas
* Pricing extraction
* Vision grounding
* Guardrails
* Perception-action loop
* Planning
* Plan execution
* Real LLM integration
* Secure login
* Self-correction
* Visual clicking

Current status:

```text
117 passed
```

---

# Test Coverage Areas

| Component                    | Tested |
| ---------------------------- | ------ |
| Browser navigation           | Yes    |
| Browser clicking             | Yes    |
| Text input                   | Yes    |
| Page reading                 | Yes    |
| Screenshots                  | Yes    |
| Vision grounding             | Yes    |
| Planner                      | Yes    |
| PlanRunner                   | Yes    |
| Perception-action loop       | Yes    |
| Self-correction              | Yes    |
| Retry limits                 | Yes    |
| Pricing extraction           | Yes    |
| Pricing schema validation    | Yes    |
| Currency normalization       | Yes    |
| Billing period normalization | Yes    |
| Secure login                 | Yes    |
| Secret redaction             | Yes    |
| Domain guardrails            | Yes    |
| Database                     | Yes    |
| End-to-end workflow          | Yes    |

---

# Design Principles

### 1. LLM proposes, deterministic code executes

The model should not be the most trusted component in the system.

The LLM generates an intended action, while deterministic code validates and executes it.

### 2. Observe before acting

The agent continuously follows:

```text
Observe
  ↓
Decide
  ↓
Act
  ↓
Observe again
```

### 3. Recover instead of blindly failing

A failed action becomes feedback for the next decision.

### 4. DOM first, vision second

Traditional browser selectors are preferred for reliability and determinism.

Vision is used when DOM-based interaction is insufficient.

### 5. Separate extraction from navigation

The browser agent gathers information.

The deterministic extraction layer decides how that information becomes structured application data.

### 6. Keep secrets outside the LLM context

Authentication is handled by a trusted layer rather than exposing raw credentials to the model.

---

# Example Workflow

A pricing extraction workflow looks like:

```text
User:
"Extract GitHub Copilot pricing"

        │
        ▼

PerSitePlanner

        │
        ▼

BrowserPlan

        │
        ▼

PlanRunner

        │
        ▼

BrowserAgent

        │
        ▼

Navigate → Search → Observe → Extract

        │
        ▼

PricingExtractor

        │
        ▼

Pydantic PricingTable

        │
        ▼

Normalized Pricing Data
```

---

# Current Version

```text
v1.0.0
```

This version represents the first complete implementation of the browser automation agent with:

* Real browser control
* LLM-based decisions
* Vision fallback
* Planning
* Self-correction
* Secure authentication
* Structured extraction
* Guardrails
* Automated tests
* Docker support

---

# Roadmap

Future improvements could include:

* Multi-site pricing extraction at larger scale
* More robust browser state tracking
* Better visual grounding
* Persistent browser sessions
* More authentication providers
* CAPTCHA/HITL handling
* Parallel browser workers
* Job queue architecture
* Observability and tracing
* Agent evaluation benchmarks
* Production API layer
* Browser task scheduling

---

# Tech Stack

| Technology | Purpose                          |
| ---------- | -------------------------------- |
| Python     | Core implementation              |
| Playwright | Browser automation               |
| Groq       | LLM inference                    |
| Pydantic   | Structured models and validation |
| LangGraph  | Agent/workflow infrastructure    |
| SQLAlchemy | Database layer                   |
| PostgreSQL | Persistence                      |
| Pytest     | Automated testing                |
| Docker     | Containerization                 |
| Chromium   | Browser runtime                  |

---

# Disclaimer

This project is intended for research, development, testing, and authorized browser automation.

Do not use it to access accounts, websites, or data without appropriate authorization.

