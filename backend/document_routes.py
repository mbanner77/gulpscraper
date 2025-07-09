"""
Document Routes for GULP Job Scraper
===================================
This module provides API routes for document upload and analysis.
"""

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import JSONResponse
from typing import List, Optional
from pydantic import BaseModel
from document_analyzer import DocumentAnalyzer

router = APIRouter()

# Reference to the document analyzer
document_analyzer = None

@router.get("/health")
async def health_check():
    """Health check endpoint for document routes."""
    import sys
    import os
    
    print("[DOCUMENT_ROUTES] Health check called")
    sys.stdout.flush()
    
    try:
        # Check dependencies
        from document_analyzer import DOCX_AVAILABLE, SPACY_AVAILABLE
        
        status = {
            "status": "ok",
            "document_analyzer_initialized": document_analyzer is not None,
            "docx_available": DOCX_AVAILABLE,
            "spacy_available": SPACY_AVAILABLE,
            "environment": {
                "render": os.environ.get('RENDER', False),
                "cloud_env": os.environ.get('CLOUD_ENV', False)
            }
        }
        
        print(f"[DOCUMENT_ROUTES] Health check status: {status}")
        sys.stdout.flush()
        
        return status
        
    except Exception as e:
        import traceback
        error_msg = f"Health check failed: {str(e)}"
        print(f"[DOCUMENT_ROUTES] ERROR: {error_msg}")
        print(f"[DOCUMENT_ROUTES] Traceback: {traceback.format_exc()}")
        sys.stderr.flush()
        
        return {
            "status": "error",
            "error": error_msg,
            "document_analyzer_initialized": document_analyzer is not None
        }

def initialize(project_mgr):
    """Initialize the document routes with project manager reference."""
    global document_analyzer
    document_analyzer = DocumentAnalyzer(project_manager=project_mgr)


class DocumentResponse(BaseModel):
    id: str
    name: str
    type: str
    size: int
    upload_date: str
    keywords: List[str]
    text_length: int


@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    document_type: str = Form("resume"),
    name: Optional[str] = Form(None)
):
    """Upload a document for analysis."""
    if not document_analyzer:
        raise HTTPException(status_code=500, detail="Document analyzer not initialized")
    
    result = await document_analyzer.process_document(file, document_type, name)
    return result


@router.get("/list")
async def list_documents():
    """List all uploaded documents."""
    import sys
    import traceback
    
    print("[DOCUMENT_ROUTES] /list endpoint called")
    sys.stdout.flush()
    
    try:
        if not document_analyzer:
            print("[DOCUMENT_ROUTES] ERROR: Document analyzer not initialized")
            sys.stderr.flush()
            raise HTTPException(status_code=500, detail="Document analyzer not initialized")
        
        documents = document_analyzer.get_documents()
        print(f"[DOCUMENT_ROUTES] Successfully retrieved {len(documents)} documents")
        sys.stdout.flush()
        
        return {"documents": documents}
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Error listing documents: {str(e)}"
        print(f"[DOCUMENT_ROUTES] ERROR: {error_msg}")
        print(f"[DOCUMENT_ROUTES] Traceback: {traceback.format_exc()}")
        sys.stderr.flush()
        raise HTTPException(status_code=500, detail=error_msg)


@router.get("/{document_id}")
async def get_document(document_id: str):
    """Get a specific document by ID."""
    if not document_analyzer:
        raise HTTPException(status_code=500, detail="Document analyzer not initialized")
    
    return document_analyzer.get_document(document_id)


@router.delete("/{document_id}")
async def delete_document(document_id: str):
    """Delete a document."""
    if not document_analyzer:
        raise HTTPException(status_code=500, detail="Document analyzer not initialized")
    
    return document_analyzer.delete_document(document_id)


@router.get("/{document_id}/compare")
async def compare_document_with_projects(document_id: str, limit: int = 10):
    """
    Compare a document with all projects and return the best matches.
    
    Args:
        document_id: ID of the document to compare
        limit: Maximum number of matches to return
    """
    if not document_analyzer:
        raise HTTPException(status_code=500, detail="Document analyzer not initialized")
    
    matches = document_analyzer.compare_with_projects(document_id, limit)
    return {"matches": matches}
