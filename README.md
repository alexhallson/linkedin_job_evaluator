# LinkedIn Job Scraper & AI Candidate Evaluator

A streamlined workflow automation tool combining a **Firefox Web Extension**, a **FastAPI local backend**, **Google Sheets**, and **OpenAI**. 

It automatically captures job postings from LinkedIn, logs them instantly to a Google Sheet, and runs an asynchronous AI analysis evaluating candidate-to-job fit against your CV using a strict, structured rubric.

---

## 🌟 Key Features

- **Automated LinkedIn Scraping**: Extract Job Title, Company, Location, URL, and full Job Description directly from LinkedIn Job pages.
- **Instant Google Sheets Logging**: Appends newly scraped jobs to a target Google Sheet immediately with a `Pending AI...` status.
- **Asynchronous AI Background Queue**: Background worker processes jobs one-by-one with intelligent rate-limiting to adhere to OpenAI API quotas.
- **Structured 4-Pillar Evaluation Rubric**:
  1. **Experience (Tenure & Industry)** (Score 0.0 - 1.0)
  2. **Skills (Technical & Domain)** (Score 0.0 - 1.0)
  3. **Visa Eligibility & Administrative Friction** (Score 0.0 - 1.0)
  4. **Cultural Fit & Company Phase Alignment** (Score 0.0 - 1.0)
- **Zero-Hardcoding CV Resolution**: Place any candidate CV (`.pdf`, `.docx`, or `.txt`) into the `CVs/` directory—the system auto-detects and uses it dynamically.
- **Automatic Startup Recovery**: Server scans Google Sheets on startup to recover and re-queue any pending jobs interrupted during previous runs.

---

## 🏗 System Architecture

```
┌─────────────────────────┐      HTTP POST       ┌─────────────────────────────────┐
│ Firefox Web Extension   │ ───────────────────> │  FastAPI Local Backend          │
│ (extension_firefox/)    │   /add-job endpoint  │  (main.py :8000)                │
└─────────────────────────┘                      └────────────────┬────────────────┘
                                                                  │
                                            ┌─────────────────────┴─────────────────────┐
                                            │                                           │
                                  1. Immediate Append                         2. Enqueue Job
                                            │                                           │
                                            ▼                                           ▼
                                ┌───────────────────────┐                  ┌─────────────────────────┐
                                │ Google Sheets         │                  │ AI Async Background     │
                                │ (Auto Job Scrapes)    │                  │ Worker (Rate Limiter)   │
                                └───────────▲───────────┘                  └────────────┬────────────┘
                                            │                                           │
                                            │ 4. Update Rows with AI Scores             │ 3. Evaluate CV
                                            └───────────────────────────────────────────┘    vs Job Description
                                                                                        │
                                                                                        ▼
                                                                           ┌─────────────────────────┐
                                                                           │ OpenAI API              │
                                                                           │ (gpt-4o-mini)           │
                                                                           └─────────────────────────┘
```

---

## 📂 Repository Structure

```
.
├── CVs/                             # User CV directory (git-ignored for privacy)
│   └── .gitkeep
├── CVs_sample/                      # Sample CV placeholder for testing
│   └── sample_cv.txt
├── extension_firefox/               # Firefox Browser Extension (Manifest V3)
│   ├── background.js
│   ├── content.js
│   └── manifest.json
├── services/                        # Modular backend services
│   ├── ai.py                        # Gemini API integration & RateLimiter
│   ├── sheets.py                    # gspread Google Sheets client
│   └── usage.py                     # API quota tracker
├── scripts/                         # Isolated utility & verification scripts
│   ├── list_models.py               # List Gemini API models via Python SDK
│   ├── list_models_curl.py          # List Gemini API models via cURL
│   └── verify_job_flow.py           # End-to-end integration test script
├── tests/                           # Unit test suite & coverage specs
├── docs/                            # Documentation guides
├── .env.example                     # Environment variable template
├── .gitignore                       # Git ignore rules for secrets, CVs & caches
├── config.py                        # Dynamic configuration & CV resolver
├── main.py                          # FastAPI application & background queue
├── models.py                        # Pydantic data schemas
├── requirements.txt                 # Python dependencies
└── CV_prompt.txt                    # Detailed AI evaluation rubric prompt
```

---

## 🚀 Getting Started

### 1. Prerequisites

- **Python 3.10+** installed.
- **Firefox Browser** (version 109+).
- **OpenAI API Key** (from [OpenAI Platform](https://platform.openai.com/)).
- **Google Cloud Service Account** with **Google Sheets API** and **Google Drive API** enabled.

---

### 2. Installation & Setup

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/your-username/linkedin_scrape_extension.git
   cd linkedin_scrape_extension
   ```

2. **Set Up Python Environment**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Configure Environment Variables**:
   Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
   Edit `.env` with your API keys:
   ```env
   OPENAI_API_KEY=your_openai_api_key_here
   GOOGLE_APPLICATION_CREDENTIALS=credentials.json
   SHEET_NAME=Auto Job Scrapes
   ```

4. **Add Google Service Account Key**:
   Download your Google Cloud Service Account JSON key file and save it in the root directory.
   The backend auto-detects common filenames such as `linkedin-data-*.json`, `credentials.json`, or `service_account.json`.
   You can also use any filename/path by setting `GOOGLE_APPLICATION_CREDENTIALS` in `.env`:
   ```env
   GOOGLE_APPLICATION_CREDENTIALS=linkedin-data-484009-fbcd1a2ffce1.json
   ```

5. **Set Up Google Sheets**:
   - Create a new Google Spreadsheet titled `Auto Job Scrapes` (or match `SHEET_NAME` in `.env`).
   - Share the spreadsheet with the `client_email` listed in your `credentials.json` (grant **Editor** permissions).

6. **Add Your CV**:
   Place your personal CV file (`.pdf`, `.docx`, or `.txt`) into the `CVs/` directory.
   > **Note**: The backend dynamically detects any CV file inside `CVs/`. If no file is present in `CVs/`, it safely falls back to `CVs_sample/sample_cv.txt`.

---

### 3. Load Firefox Web Extension

1. Open Firefox and navigate to `about:debugging#/runtime/this-firefox`.
2. Click **Load Temporary Add-on...**.
3. Select the `manifest.json` file inside `extension_firefox/`.

---

## 🏃 Running the Application

1. **Start the FastAPI Backend**:
   ```bash
   python main.py
   ```
   Or using Uvicorn directly:
   ```bash
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

2. **Scrape Jobs on LinkedIn**:
   - Open Firefox and navigate to any LinkedIn Job search or job post (`https://www.linkedin.com/jobs/*`).
   - Click on a job posting to view its details.
   - The extension automatically extracts the job data and sends it to `http://localhost:8000/add-job`.
   - Check your Google Sheet to see the job logged immediately and updated with AI scores shortly after.

3. **Run End-to-End Verification Test**:
   ```bash
   python scripts/verify_job_flow.py
   ```

4. **Run Unit Tests & Coverage**:
   ```bash
   pytest --cov=. --cov-report=term-missing
   ```
   > For a plain English non-technical breakdown of the AI tests, see [docs/test_ai_explanation.md](docs/test_ai_explanation.md).

---

## 📊 Evaluation Rubric

The AI evaluates job postings against the candidate CV according to the criteria defined in `CV_prompt.txt`:

| Pillar | Focus | Score Range |
| :--- | :--- | :--- |
| **Experience** | Industry tenure, direct sector background, and seniority alignment | 0.0 - 1.0 |
| **Skills** | Technical proficiencies, mandatory vs. preferred skills coverage | 0.0 - 1.0 |
| **Visa Eligibility** | Onboarding friction, legal work authorization, sponsorship requirements | 0.0 - 1.0 |
| **Cultural Fit** | Company phase alignment (e.g. early startup vs enterprise), work pace | 0.0 - 1.0 |

---

## 🔒 Security & Privacy Notice

- **Personal Data**: The `CVs/` folder and root credential files are explicitly ignored in `.gitignore`. **Never commit personal CVs or API keys to a public repository.**
- **Service Account Keys**: Keep `credentials.json` confidential and untracked.

---

## 📄 License

This project is open-source and available under the [MIT License](LICENSE).
