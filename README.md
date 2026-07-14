AI-Powered ATS Resume Optimizer

Overview

The AI ATS Resume Optimizer is a full-stack, AI-driven application designed to help job seekers beat Applicant Tracking Systems (ATS). By leveraging a multi-tier LLM cascade architecture (OpenRouter, Groq, SambaNova, Gemini), the tool extracts resume data, calculates deterministic ATS match scores against Job Descriptions, and automatically generates actionable, keyword-optimized bullet points.

Key Features

Multi-LLM Cascading Fallback: Ensures 100% uptime by routing failed AI requests through 4 different global AI providers with a 10-second fail-fast timeout.

Smart JD Matching: Analyzes job descriptions to calculate a 0-100% keyword match and explicitly maps missing skills.

AI Bullet Generation: Contextually rewrites weak resume bullet points to align perfectly with target job descriptions.

Auto-Healing JSON Parser: Intelligently corrects malformed LLM outputs and missing brackets before they crash the application.

Native DOCX Export: Dynamically generates a clean, standardized, 100% ATS-readable .docx resume for the user to download.

Technology Stack

Frontend: Streamlit

Backend Core: Python 3

AI/LLM Providers: OpenRouter (NVIDIA/Tencent), Groq (Llama 3), SambaNova, Google Gemini

Document Parsing: pypdf, python-docx

Architecture: Fault-tolerant API routing, JSON auto-healing

How to Run Locally

Clone the repository:

git clone https://github.com/YourUsername/AI-Resume-Analyzer.git


Install dependencies:

pip install -r requirements.txt


Set up environment variables in a .env file:

OPENROUTER_API_KEY_MAIN=your_key
GROQ_API_KEY=your_key
SAMBANOVA_API_KEY=your_key
GEMINI_API_KEY=your_key


Run the application:

streamlit run app.py
