# NDA Analysis Comparison Tool

## Overview

This is a Streamlit web application that compares AI-generated NDA (Non-Disclosure Agreement) reviews with HR-edited versions to assess the accuracy and coverage of AI analysis. The system analyzes legal documents using Google's Gemini AI models and provides comparative insights between automated AI reviews and human HR edits.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Frontend Architecture
- **Framework**: Streamlit web application
- **UI Components**: File upload widgets, configuration panels, results display sections
- **Visualization**: Plotly charts for metrics visualization
- **State Management**: Streamlit session state for maintaining application state

### Backend Architecture
- **Core Processing**: Python-based modular architecture
- **AI Integration**: LangChain framework with Google Generative AI (Gemini models)
- **Document Processing**: Multi-format document loaders (PDF, DOCX, TXT, MD)
- **Data Models**: Pydantic models for structured data validation and parsing

## Key Components

### 1. Document Analysis Modules
- **NDA_Review_chain.py**: Primary AI reviewer for analyzing clean NDAs against company playbook
- **NDA_HR_review_chain.py**: Analyzes NDAs with tracked changes to identify HR compliance modifications
- **Clean_testing.py**: Orchestrates comparative analysis between AI and HR reviews

### 2. Web Application
- **app.py**: Main Streamlit application with user interface and workflow management
- **utils.py**: Utility functions for file validation, JSON parsing, and chart generation

### 3. Data Models
- **ComplianceFlag**: Individual compliance issues with structured fields (issue, citation, section, problem, suggested_replacement)
- **ComplianceReport**: Complete compliance analysis with red_flags and yellow_flags categorization

## Data Flow

1. **Document Upload**: Users upload original NDA and HR-corrected version
2. **AI Analysis**: System processes both documents through separate analysis chains
3. **Comparison Engine**: Compares AI findings with HR edits to identify matches, misses, and false positives
4. **Results Generation**: Produces structured comparison results with accuracy metrics
5. **Visualization**: Displays results through interactive charts and detailed breakdowns

## External Dependencies

### AI Services
- **Google Generative AI**: Primary AI model provider (Gemini 2.5 Flash/Pro)
- **LangChain**: Framework for AI chain orchestration and prompt management

### Document Processing
- **PyPDF2/PyPDFLoader**: PDF document parsing
- **python-docx/Docx2txtLoader**: Word document processing
- **TextLoader**: Plain text and markdown file handling

### Web Framework
- **Streamlit**: Web application framework
- **Plotly**: Interactive data visualization
- **Pandas**: Data manipulation and analysis

### Environment Management
- **python-dotenv**: Environment variable management for API keys

## Deployment Strategy

### Environment Setup
- Requires Google AI API key configuration
- Environment variables managed through .env file
- Python dependencies managed through requirements.txt (implied)

### Application Structure
- Single-page Streamlit application with modular backend
- Session state management for user workflow persistence
- File upload handling with validation and temporary storage

### Configuration Options
- Model selection (Gemini 2.5 Flash vs Pro)
- Temperature control for AI generation
- Analysis mode selection (Full Analysis vs Quick Testing)

### Data Security
- Temporary file handling for uploaded documents
- No persistent storage of uploaded legal documents
- API key protection through environment variables

## Technical Notes

The application uses a sophisticated prompt engineering approach with persona-based AI instructions, treating the AI as "LexAI, a senior M&A lawyer and diligence analyst." The system supports multiple analysis modes and provides detailed reconciliation between AI-generated reviews and human HR edits, making it suitable for legal compliance verification workflows.