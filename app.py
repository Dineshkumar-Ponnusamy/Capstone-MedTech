#!/usr/bin/env python3
"""
FastAPI Web UI for Medical Device Compliance Reviewer
Runs with: uvicorn app:app --reload --host 0.0.0.0 --port 8000
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import aiofiles
from dotenv import load_dotenv

# Add src to path
import sys
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Load environment variables from .env for local runs
load_dotenv()

from src.coordinator_simple import SimpleAdvancedCoordinator
from src.utils.config import config
from src.utils.job_store import JobStore

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Validate configuration on startup
if not config.validate_config():
    logger.error("Configuration validation failed. Please check config.yaml and environment variables.")
    raise RuntimeError("Configuration validation failed")

# Create FastAPI app
app = FastAPI(
    title="Medical Device Compliance Reviewer",
    description="Advanced multi-agent compliance review system using Google ADK",
    version="1.0.0"
)

# Add CORS middleware with security restrictions
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8080", "http://127.0.0.1:3000"],  # Restrict origins
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)

# Global state for tracking jobs with cleanup
import threading
import time
from datetime import timedelta

job_store = JobStore()
job_cleanup_interval = 3600  # 1 hour
max_job_age = 86400  # 24 hours


def _safe_delete_file(path: str) -> None:
    """Best-effort delete for temp uploads."""
    try:
        if path and os.path.exists(path):
            os.remove(path)
            logger.info(f"Deleted temp file: {path}")
    except Exception as e:
        logger.warning(f"Could not delete temp file {path}: {e}")

def cleanup_old_jobs():
    """Remove jobs older than max_job_age (24 hours)."""
    removed = job_store.cleanup_old_jobs(
        max_age_seconds=max_job_age,
        completed_or_failed_age_seconds=3600
    )
    for job_id in removed:
        logger.info(f"Cleaned up old job: {job_id}")

def start_job_cleanup_worker():
    """Start the background job cleanup worker."""
    def cleanup_worker():
        while True:
            try:
                cleanup_old_jobs()
                time.sleep(job_cleanup_interval)
            except Exception as e:
                logger.error(f"Error in job cleanup worker: {e}")
                time.sleep(300)  # Retry after 5 minutes
    
    cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
    cleanup_thread.start()
    logger.info("Job cleanup worker started")

# Start the cleanup worker
start_job_cleanup_worker()


@app.get("/", response_class=HTMLResponse)
async def get_home():
    """Serve the main web UI."""
    return HTML_TEMPLATE


@app.post("/api/analyze")
async def analyze_document(
    file: UploadFile = File(...),
    device_class: str = "Class II",
    intended_use: str = "Medical device",
    regulatory_path: str = "FDA 510(k)",
    background_tasks: BackgroundTasks = None
):
    """
    Analyze a medical device requirements document.
    
    Returns a job ID for tracking progress.
    """
    try:
        # Validate file
        if not file.filename:
            raise HTTPException(status_code=400, detail="No file provided")
        
        # Validate file extension and format
        allowed_extensions = {'.txt', '.pdf', '.docx', '.doc', '.csv', '.md'}
        file_extension = Path(file.filename).suffix.lower()
        if file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported file format. Allowed: {', '.join(allowed_extensions)}"
            )
        
        # Validate filename for security (prevent path traversal)
        if '..' in file.filename or '/' in file.filename or '\\' in file.filename:
            raise HTTPException(status_code=400, detail="Invalid filename")
        
        # Read once and check file size (limit to 10MB)
        content_bytes = await file.read()
        if len(content_bytes) > 10 * 1024 * 1024:  # 10MB limit
            raise HTTPException(
                status_code=400,
                detail="File too large (max 10MB). Please upload a file under 10MB."
            )
        
        # Create secure job ID with random component
        import secrets
        random_suffix = secrets.token_hex(8)
        job_id = f"job_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{random_suffix}"
        
        # Save uploaded file temporarily (keep original bytes for downstream parsing)
        temp_path = f"data/uploads/{job_id}_{file.filename}"
        Path(temp_path).parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(temp_path, 'wb') as f:
            await f.write(content_bytes)
        
        # Initialize job state with persistence
        job_info = {
            "status": "processing",
            "file": file.filename,
            "start_time": datetime.now().isoformat(),
            "progress": 0,
            "result": None,
            "error": None,
            "file_path": temp_path
        }
        
        job_store.create_job(job_id, job_info)
        
        # Process in background
        if background_tasks:
            background_tasks.add_task(
                process_compliance_review,
                job_id,
                temp_path,
                device_class,
                intended_use,
                regulatory_path
            )
        else:
            # Process synchronously if no background tasks
            asyncio.create_task(
                process_compliance_review(
                    job_id,
                    temp_path,
                    device_class,
                    intended_use,
                    regulatory_path
                )
            )
        
        return {
            "job_id": job_id,
            "status": "processing",
            "message": "Analysis started"
        }
    
    except Exception as e:
        logger.error(f"Error in analyze_document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/job/{job_id}")
async def get_job_status(job_id: str):
    """Get the status of a compliance analysis job."""
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return {
        "job_id": job_id,
        "status": job["status"],
        "progress": job["progress"],
        "file": job["file"],
        "start_time": job["start_time"],
        "result": job["result"],
        "error": job["error"]
    }


@app.get("/api/job/{job_id}/report")
async def get_job_report(job_id: str):
    """Download the compliance report for a job."""
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    if job["status"] != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Job still processing. Status: {job['status']}"
        )
    
    if job["error"]:
        raise HTTPException(
            status_code=400,
            detail=f"Job failed: {job['error']}"
        )
    
    # Return report as JSON file
    report_filename = f"compliance_report_{job_id}.json"
    return JSONResponse(
        content=job["result"],
        headers={"Content-Disposition": f"attachment; filename={report_filename}"}
    )


@app.get("/api/jobs")
async def list_jobs():
    """List all jobs with their status."""
    jobs = job_store.list_jobs()
    return {
        "total_jobs": len(jobs),
        "jobs": [
            {
                "job_id": job["job_id"],
                "status": job["status"],
                "file": job["file"],
                "start_time": job["start_time"],
                "progress": job["progress"]
            }
            for job in jobs
        ]
    }


@app.delete("/api/job/{job_id}")
async def delete_job(job_id: str):
    """Delete a job and its data."""
    job_info = job_store.delete_job(job_id)
    if not job_info:
        raise HTTPException(status_code=404, detail="Job not found")
    
    _safe_delete_file(job_info.get("file_path"))
    
    return {"message": f"Job {job_id} deleted"}


async def process_compliance_review(
    job_id: str,
    file_path: str,
    device_class: str,
    intended_use: str,
    regulatory_path: str
):
    """Process compliance review in background."""
    try:
        job_store.update_job(job_id, {"progress": 10})
        
        # Initialize coordinator
        coordinator = SimpleAdvancedCoordinator()
        job_store.update_job(job_id, {"progress": 20})
        
        # Process document
        result = await coordinator.process_document(
            file_path,
            additional_context={
                "device_class": device_class,
                "intended_use": intended_use,
                "regulatory_path": regulatory_path
            }
        )
        
        job_store.update_job(job_id, {
            "progress": 100,
            "result": result,
            "status": "completed"
        })
        
        logger.info(f"Job {job_id} completed successfully")
    
    except Exception as e:
        logger.error(f"Error processing job {job_id}: {e}", exc_info=True)
        job_store.update_job(job_id, {
            "status": "failed",
            "error": str(e)
        })
    finally:
        _safe_delete_file(file_path)


# HTML Template for web UI
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Medical Device Compliance Reviewer</title>
    <style>
        :root {
            --primary: #0ea5e9;
            --secondary: #7c3aed;
            --accent: #ec4899;
            --text: #1a202c;
            --text-light: #4a5568;
            --bg-primary: #f8fafc;
            --bg-secondary: #ffffff;
            --shadow: rgba(0, 0, 0, 0.1);
            --border: #e2e8f0;
            --success: #0d9488;
            --warning: #f59e0b;
            --error: #ef4444;
            --radius: 8px;
        }

        [data-theme="dark"] {
            --primary: #38bdf8;
            --secondary: #8b5cf6;
            --accent: #f472b6;
            --text: #f7fafc;
            --text-light: #a0aec0;
            --bg-primary: #1a202c;
            --bg-secondary: #2d3748;
            --shadow: rgba(0, 0, 0, 0.3);
            --border: #4a5568;
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', Oxygen, Ubuntu, Cantarell, sans-serif;
            background: var(--bg-primary);
            min-height: 100vh;
            color: var(--text);
            transition: all 0.3s ease;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }

        .theme-toggle {
            position: fixed;
            top: 20px;
            right: 20px;
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 10px;
            cursor: pointer;
            z-index: 1000;
            transition: all 0.3s ease;
            box-shadow: 0 2px 10px var(--shadow);
        }

        .theme-toggle:hover {
            transform: scale(1.05);
        }

        .theme-toggle::before {
            content: '🌙';
        }

        [data-theme="dark"] .theme-toggle::before {
            content: '☀️';
        }

        header {
            background: var(--bg-secondary);
            border-radius: var(--radius);
            padding: 40px 30px;
            margin-bottom: 40px;
            box-shadow: 0 20px 40px var(--shadow);
            border: 1px solid var(--border);
            position: relative;
            overflow: hidden;
        }

        header::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: linear-gradient(135deg, var(--primary), var(--secondary));
            opacity: 0.05;
        }

        header h1,
        header p {
            position: relative;
            z-index: 1;
        }

        header h1 {
            color: var(--text);
            font-size: 32px;
            font-weight: 700;
            margin-bottom: 10px;
            animation: fadeIn 0.8s ease;
        }

        header p {
            color: var(--text-light);
            font-size: 16px;
            max-width: 600px;
        }

        .main {
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 30px;
            margin-bottom: 30px;
        }

        .card {
            background: var(--bg-secondary);
            border-radius: var(--radius);
            padding: 30px;
            box-shadow: 0 10px 30px var(--shadow);
            border: 1px solid var(--border);
            transition: all 0.3s ease;
            animation: slideIn 0.6s ease;
        }

        .card:hover {
            transform: translateY(-2px);
            box-shadow: 0 20px 50px var(--shadow);
        }

        .card h2 {
            color: var(--text);
            font-size: 24px;
            margin-bottom: 25px;
            border-bottom: 3px solid var(--primary);
            padding-bottom: 15px;
            font-weight: 600;
        }

        .form-group {
            margin-bottom: 20px;
        }

        label {
            display: block;
            color: var(--text);
            font-weight: 600;
            margin-bottom: 8px;
            font-size: 14px;
        }

        input[type="text"],
        input[type="file"],
        select {
            width: 100%;
            padding: 14px 16px;
            border: 1px solid var(--border);
            border-radius: var(--radius);
            font-size: 16px;
            font-family: inherit;
            background: var(--bg-secondary);
            color: var(--text);
            transition: all 0.3s ease;
        }

        input[type="text"]:focus,
        input[type="file"]:focus,
        select:focus {
            outline: none;
            border-color: var(--primary);
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }

        input[type="file"] {
            cursor: pointer;
        }

        button {
            background: linear-gradient(135deg, var(--primary), var(--secondary));
            color: white;
            border: none;
            padding: 16px 32px;
            border-radius: var(--radius);
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            width: 100%;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
        }

        button:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(102, 126, 234, 0.4);
        }

        button:active {
            transform: translateY(0);
        }

        button:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            transform: none;
        }

        .status-box {
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            padding: 20px;
            border-radius: var(--radius);
            margin-bottom: 20px;
            display: none;
            animation: fadeInUp 0.5s ease;
        }

        .status-box.show {
            display: block;
        }

        .status-label {
            font-weight: 700;
            color: var(--text);
            font-size: 14px;
            margin-bottom: 8px;
        }

        .status-value {
            color: var(--primary);
            font-size: 16px;
            font-weight: 600;
        }

        .progress-bar {
            background: var(--border);
            height: 8px;
            border-radius: 4px;
            margin-top: 15px;
            overflow: hidden;
        }

        .progress-fill {
            background: linear-gradient(90deg, var(--primary), var(--secondary));
            height: 100%;
            width: 0%;
            transition: width 0.5s ease;
        }

        .jobs-list {
            max-height: 500px;
            overflow-y: auto;
            scroll-behavior: smooth;
        }

        .job-item {
            background: var(--bg-secondary);
            padding: 16px;
            border-left: 4px solid var(--primary);
            margin-bottom: 12px;
            border-radius: var(--radius);
            display: flex;
            justify-content: space-between;
            align-items: center;
            border: 1px solid var(--border);
            transition: all 0.3s ease;
            animation: slideIn 0.4s ease;
        }

        .job-item:hover {
            transform: translateX(5px);
            background: var(--bg-primary);
        }

        .job-info {
            flex: 1;
        }

        .job-id {
            font-weight: 600;
            color: var(--text);
            font-size: 14px;
            margin-bottom: 4px;
        }

        .job-status {
            font-size: 12px;
            color: var(--text-light);
            margin-top: 6px;
        }

        .job-status.completed {
            color: var(--success);
        }

        .job-status.processing {
            color: var(--warning);
        }

        .job-status.failed {
            color: var(--error);
        }

        .btn-small {
            background: var(--primary);
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: var(--radius);
            font-size: 13px;
            cursor: pointer;
            transition: all 0.3s ease;
        }

        .btn-small:hover {
            background: var(--secondary);
            transform: scale(1.05);
        }

        .report-card {
            margin-top: 30px;
            grid-column: 1 / -1;
        }

        .empty-state {
            text-align: center;
            color: var(--text-light);
            padding: 60px 20px;
            animation: pulse 2s infinite;
        }

        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }

        @keyframes slideIn {
            from { transform: translateY(20px); opacity: 0; }
            to { transform: translateY(0); opacity: 1; }
        }

        @keyframes fadeInUp {
            from { transform: translateY(30px); opacity: 0; }
            to { transform: translateY(0); opacity: 1; }
        }

        @keyframes pulse {
            0%, 100% { opacity: 0.5; }
            50% { opacity: 1; }
        }

        @media (max-width: 1024px) {
            .main {
                grid-template-columns: 1fr;
            }
        }

        @media (max-width: 768px) {
            .container {
                padding: 15px;
            }

            header {
                padding: 30px 20px;
            }

            header h1 {
                font-size: 24px;
            }

            .card {
                padding: 20px;
            }

            .main {
                gap: 20px;
            }

            .theme-toggle {
                position: relative;
                top: auto;
                right: auto;
                margin-bottom: 20px;
            }
        }
    </style>
</head>
<body>
    <div class="theme-toggle" onclick="toggleTheme()" title="Toggle Dark/Light Theme"></div>

    <div class="container">
        <header>
            <h1>🏥 Medical Device Compliance Reviewer</h1>
            <p>Advanced multi-agent analysis powered by Google ADK with ParallelAgent and LoopAgent patterns</p>
        </header>

        <div class="main">
            <!-- Upload Section -->
            <div class="card">
                <h2>📤 Upload & Analyze</h2>

                <div class="form-group">
                    <label>Requirements Document</label>
                    <input type="file" id="fileInput" accept=".txt,.pdf,.docx,.md">
                    <small style="color: var(--text-light); margin-top: 5px; display: block;">Supported: .txt, .pdf, .docx, .md</small>
                </div>

                <div class="form-group">
                    <label>Device Class</label>
                    <select id="deviceClass">
                        <option value="Class I">Class I (Low Risk)</option>
                        <option value="Class II" selected>Class II (Medium Risk)</option>
                        <option value="Class III">Class III (High Risk)</option>
                    </select>
                </div>

                <div class="form-group">
                    <label>Intended Use</label>
                    <input type="text" id="intendedUse" placeholder="e.g., Patient monitoring in clinical settings" value="Patient monitoring">
                </div>

                <div class="form-group">
                    <label>Regulatory Path</label>
                    <select id="regulatoryPath">
                        <option value="FDA 510(k)" selected>FDA 510(k)</option>
                        <option value="FDA PMA">FDA PMA</option>
                        <option value="CE Mark">CE Mark (EU)</option>
                        <option value="PMDA">PMDA (Japan)</option>
                    </select>
                </div>

                <button onclick="submitAnalysis()" id="submitBtn">🚀 Start Analysis</button>

                <div class="status-box" id="statusBox">
                    <div class="status-label">Analysis Status</div>
                    <div class="status-value" id="statusText">Initializing...</div>
                    <div class="progress-bar">
                        <div class="progress-fill" id="progressFill"></div>
                    </div>
                </div>
            </div>

            <!-- Results Section -->
            <div class="card">
                <h2>📊 Recent Jobs</h2>
                <div class="jobs-list" id="jobsList">
                    <div class="empty-state">No jobs yet. Upload a document to get started.</div>
                </div>
            </div>
        </div>

        <!-- Full-width Results -->
        <div class="card report-card">
            <h2>📋 Compliance Report</h2>
            <div id="reportContainer" style="display: none;">
                <div id="reportContent"></div>
                <button onclick="downloadReport()" style="margin-top: 20px; background: var(--success);">📥 Download Report</button>
            </div>
            <div id="reportEmpty" class="empty-state">
                Complete an analysis to view the compliance report here.
            </div>
        </div>
    </div>

    <script>
        let currentJobId = null;
        let pollInterval = null;

        async function submitAnalysis() {
            const fileInput = document.getElementById('fileInput');
            const file = fileInput.files[0];
            if (!file) {
                alert('Please select a file');
                return;
            }

            const formData = new FormData();
            formData.append('file', file);
            formData.append('device_class', document.getElementById('deviceClass').value);
            formData.append('intended_use', document.getElementById('intendedUse').value);
            formData.append('regulatory_path', document.getElementById('regulatoryPath').value);

            const btn = document.getElementById('submitBtn');
            btn.disabled = true;
            btn.textContent = '⏳ Processing...';

            try {
                const response = await fetch('/api/analyze', {
                    method: 'POST',
                    body: formData
                });

                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }

                const data = await response.json();
                currentJobId = data.job_id;

                document.getElementById('statusBox').classList.add('show');
                document.getElementById('reportEmpty').style.display = 'block';
                document.getElementById('reportContainer').style.display = 'none';

                // Start polling
                pollJobStatus();
                pollInterval = setInterval(pollJobStatus, 1000);

            } catch (error) {
                alert('Error submitting analysis: ' + error.message);
                btn.disabled = false;
                btn.textContent = '🚀 Start Analysis';
            }
        }

        async function pollJobStatus() {
            if (!currentJobId) return;

            try {
                const response = await fetch(`/api/job/${currentJobId}`);
                const job = await response.json();

                document.getElementById('statusText').textContent = `Status: ${job.status.toUpperCase()} (${job.progress}%)`;
                document.getElementById('progressFill').style.width = job.progress + '%';

                if (job.status === 'completed') {
                    clearInterval(pollInterval);
                    document.getElementById('submitBtn').disabled = false;
                    document.getElementById('submitBtn').textContent = '🚀 Start Analysis';

                    // Show report
                    displayReport(job.result);
                    updateJobsList();

                } else if (job.status === 'failed') {
                    clearInterval(pollInterval);
                    document.getElementById('statusText').textContent = `Error: ${job.error}`;
                    document.getElementById('submitBtn').disabled = false;
                    document.getElementById('submitBtn').textContent = '🚀 Start Analysis';
                }

                updateJobsList();

            } catch (error) {
                console.error('Error polling job status:', error);
            }
        }

        async function updateJobsList() {
            try {
                const response = await fetch('/api/jobs');
                const data = await response.json();

                const jobsList = document.getElementById('jobsList');

                if (data.jobs.length === 0) {
                    jobsList.innerHTML = '<p style="color: #999; text-align: center; padding: 30px 0;">No jobs yet.</p>';
                    return;
                }

                jobsList.innerHTML = data.jobs
                    .sort((a, b) => new Date(b.start_time) - new Date(a.start_time))
                    .slice(0, 10)
                    .map(job => `
                        <div class="job-item">
                            <div class="job-info">
                                <div class="job-id">${job.job_id.substring(0, 30)}...</div>
                                <div class="job-status ${job.status}">${job.status.toUpperCase()} - ${job.file}</div>
                                <small style="color: #999;">${job.progress}% complete</small>
                            </div>
                            <button class="btn-small" onclick="selectJob('${job.job_id}')">View</button>
                        </div>
                    `).join('');

            } catch (error) {
                console.error('Error updating jobs list:', error);
            }
        }

        async function selectJob(jobId) {
            try {
                const response = await fetch(`/api/job/${jobId}`);
                const job = await response.json();

                if (job.status === 'completed' && job.result) {
                    currentJobId = jobId;
                    displayReport(job.result);
                } else {
                    alert(`Job status: ${job.status}`);
                }
            } catch (error) {
                alert('Error loading job: ' + error.message);
            }
        }

        function displayReport(result) {
            const container = document.getElementById('reportContainer');
            const empty = document.getElementById('reportEmpty');

            if (!result) {
                empty.style.display = 'block';
                container.style.display = 'none';
                return;
            }

            const html = `
                <div style="margin-bottom: 20px;">
                    <h3 style="color: var(--text); margin-bottom: 10px;">Analysis Summary</h3>
                    <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
                        <tr style="background: var(--bg-secondary);">
                            <td style="padding: 10px; border: 1px solid var(--border); color: var(--text);"><strong>Status</strong></td>
                            <td style="padding: 10px; border: 1px solid var(--border); color: var(--text);">${result.status || 'N/A'}</td>
                        </tr>
                        <tr>
                            <td style="padding: 10px; border: 1px solid var(--border); color: var(--text);"><strong>Coordinator</strong></td>
                            <td style="padding: 10px; border: 1px solid var(--border); color: var(--text);">${result.metadata?.coordinator || 'N/A'}</td>
                        </tr>
                        <tr style="background: var(--bg-secondary);">
                            <td style="padding: 10px; border: 1px solid var(--border); color: var(--text);"><strong>Agents</strong></td>
                            <td style="padding: 10px; border: 1px solid var(--border); color: var(--text);">${result.metadata?.total_specialist_agents || 0}</td>
                        </tr>
                        <tr>
                            <td style="padding: 10px; border: 1px solid var(--border); color: var(--text);"><strong>Human Reviews</strong></td>
                            <td style="padding: 10px; border: 1px solid var(--border); color: var(--text);">${result.metadata?.human_reviews_triggered || 0}</td>
                        </tr>
                        <tr style="background: var(--bg-secondary);">
                            <td style="padding: 10px; border: 1px solid var(--border); color: var(--text);"><strong>Compliance Status</strong></td>
                            <td style="padding: 10px; border: 1px solid var(--border); color: var(--text);">${result.compliance_summary?.overall_compliance_status || 'N/A'}</td>
                        </tr>
                    </table>
                </div>

                <div style="margin-bottom: 20px;">
                    <h3 style="color: var(--text); margin-bottom: 10px;">Specialist Agents</h3>
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px;">
                        ${(result.specialist_analyses || []).map(agent => `
                            <div style="background: var(--bg-secondary); color: var(--text); padding: 12px; border-radius: var(--radius); border: 1px solid var(--border);">
                                <strong style="color: var(--text); display: block; margin-bottom: 5px;">${agent.agent || 'Unknown'}</strong>
                                <small style="color: var(--text-light);">Status: ${agent.status || 'N/A'}</small><br>
                                <small style="color: var(--text-light);">Issues: ${(agent.issues || []).length}</small>
                            </div>
                        `).join('')}
                    </div>
                </div>

                <details style="margin-top: 20px; border-top: 1px solid var(--border); padding-top: 20px;">
                    <summary style="cursor: pointer; color: var(--primary); font-weight: 600;">View Full Report (JSON)</summary>
                    <pre style="background: var(--bg-secondary); color: var(--text); padding: 15px; border-radius: var(--radius); overflow-x: auto; font-size: 11px; border: 1px solid var(--border);"> ${JSON.stringify(result, null, 2)}</pre>
                </details>
            `;

            document.getElementById('reportContent').innerHTML = html;
            container.style.display = 'block';
            empty.style.display = 'none';
        }

        function downloadReport() {
            if (!currentJobId) {
                alert('No job selected');
                return;
            }

            window.location.href = `/api/job/${currentJobId}/report`;
        }

        function toggleTheme() {
            const html = document.documentElement;
            const currentTheme = html.getAttribute('data-theme');
            if (currentTheme === 'dark') {
                html.removeAttribute('data-theme');
            } else {
                html.setAttribute('data-theme', 'dark');
            }
        }

        // Initialize theme based on user preference
        const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        if (prefersDark) {
            document.documentElement.setAttribute('data-theme', 'dark');
        }

        // Load jobs on page load
        updateJobsList();
        setInterval(updateJobsList, 5000);
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
