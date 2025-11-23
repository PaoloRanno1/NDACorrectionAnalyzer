# NDA Analysis Comparison Tool

## Overview

This Streamlit web application compares AI-generated NDA (Non-Disclosure Agreement) reviews with HR-edited versions to evaluate the accuracy, coverage, and reliability of AI analysis. The system uses Google’s Gemini AI models to assess legal documents and provides a structured comparison between automated AI reviews and human edits.

## User Preferences
- **Preferred communication style:** Simple, everyday language.

---

## System Architecture

### Frontend Architecture
- **Framework:** Streamlit web application  
- **UI Components:** File upload widgets, configuration panels, results display sections  
- **Visualization:** Plotly charts for metrics visualization  
- **State Management:** Streamlit session state  

### Backend Architecture
- **Core Processing:** Modular Python backend  
- **AI Integration:** LangChain + Google Gemini (2.5 Flash/Pro)  
- **Document Processing:** Multi-format loaders (PDF, DOCX, TXT, MD)  
- **Data Models:** Pydantic-based structured models  

---

## Key Components

### 1. Document Analysis Modules
- **`NDA_Review_chain.py`** — AI reviewer for clean NDAs based on the playbook  
- **`NDA_HR_review_chain.py`** — Analyzer for NDAs with tracked changes  
- **`Clean_testing.py`** — Comparative engine between AI and HR reviews  

### 2. Web Application
- **`app.py`** — Main Streamlit interface  
- **`utils.py`** — File validation, JSON parsing, charting utilities  

### 3. Data Models
- **ComplianceFlag:**  
  Structured representation of individual issues:  
  `issue`, `citation`, `section`, `problem`, `suggested_replacement`.

- **ComplianceReport:**  
  Complete, priority-based analysis:  
  - 🔴 **High Priority (Policies 1–5):** Mandatory changes  
  - 🟡 **Medium Priority (Policies 6–10):** Preferential changes  
  - 🟢 **Low Priority (Policies 11–14):** Optional changes  

---

## Data Flow

1. **Document Upload:** Original NDA + HR-corrected version  
2. **AI Analysis:** Both documents processed through dedicated analysis chains  
3. **Comparison Engine:** Matches AI findings with HR edits to find overlaps, misses, false positives  
4. **Results Generation:** Produces structured JSON results with metrics  
5. **Visualization:** Interactive charts + detailed breakdowns  

---

## External Dependencies

### AI Services
- **Google Generative AI:** Gemini 2.5 Flash/Pro  
- **LangChain:** Prompting and chain management  

### Document Processing
- PyPDF2 / PyPDFLoader  
- python-docx / Docx2txtLoader  
- TextLoader  

### Web Framework & Visualization
- Streamlit  
- Plotly  
- Pandas  

### Environment Management
- python-dotenv for API key handling  

---

## Deployment Strategy

### Environment Setup
- Requires Google AI API key  
- `.env` file for environment variables  
- Python dependencies via `requirements.txt`  

### Application Structure
- Single-page Streamlit app with modular backend  
- Session state for workflow persistence  
- Temp file handling for uploads  

### Configuration Options
- Model selection (Flash / Pro)  
- Temperature adjustment  
- Analysis mode (Full vs Quick)  

### Data Security
- Temporary handling only—no permanent storage  
- Secure API key usage  

---

## Technical Notes

The system relies on a persona-based prompt engineering approach, treating the AI as:

> **“LexAI, a senior M&A lawyer and diligence analyst.”**

Multiple analysis modes are supported, along with reconciliation between AI findings and HR changes for compliance verification.

---

# Recent Changes (January 2025)

## Priority System Implementation
- Replaced red/yellow flag system with **High/Medium/Low Priority** categories  
- Updated all analysis modules to use priority-based results  
- Enhanced JSON parsing with better error handling  
- Updated UI with colored priority indicators (🔴🟡🟢)  
- Standardized temperature defaults to **0.0**  

---

## Editable Playbook Feature
- **Dynamic playbook system** via `playbook_manager.py`  
- Playbook content fully editable in the UI  
- Stored in session state with save/reset options  
- Chains automatically load updated playbook  
- Backwards compatible with default playbook  

---

## Navigation Structure Update
- Added a comprehensive **Homepage** with feature descriptions  
- Page-based navigation using session state  
- Persistent navigation bar (Review, Testing, Database, Policies, FAQ)  
- Each feature separated into its own UI page  
- Added JSON viewer in Clean NDA Review  
- Restored Database as a main navigation tab  

---

## Test Database System
- Added `test_data/` directory with standardized naming  
- `test_database.py` enables automatic NDA discovery  
- Testing UI allows selecting project test cases  
- First example added: **Project Octagon**  
- Custom uploads still supported  

---

## Results Management System
- Added `results_manager.py` for saving/loading results  
- “Save Results” button with custom naming  
- **Testing Results** page for browsing previous outputs  
- Stores HTML + PNG versions of Plotly charts  
- Metadata and timestamps recorded  
- Auto-cleanup: keeps only **last 2 results per project**  
- Detailed analytics dashboard including:  
  - Accuracy, precision, recall  
  - All AI findings by priority  
  - All HR edits by priority  
  - Missed issues  
  - Project comparison table  
  - Expandable detailed views  

---

## Database Tab Enhancements
- Full CRUD system for clean/corrected NDAs  
- Automatic project status detection  
- Individual file upload support  
- Integration with NDA Review tab  
- Comprehensive project tracking table  

---

## Post-Review Editing Feature
- “Edit Selected Issues” button after AI analysis  
- Priority-organized issue selection with checkboxes  
- Comment fields for user notes  
- LLM-powered text processing using tracked-changes utilities  
- Generates both **tracked-changes DOCX** and **clean DOCX**  
- Requires DOCX input for editing  
- Demo mode available if DOCX dependencies missing  
- Full workflow:  
  **AI analysis → issue selection → user comments → AI processing → document generation**  
- Removed JSON Data Viewer from results (as requested)  

---
