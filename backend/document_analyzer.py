"""
Document Analyzer for GULP Job Scraper
=====================================
This module provides functionality to analyze Word documents and compare them with projects.
"""

import os
import json
import time
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
import docx2txt
from fastapi import UploadFile, HTTPException
import spacy
from collections import Counter

# Load German language model for NLP processing
try:
    nlp = spacy.load("de_core_news_sm")
except Exception as e:
    print(f"Warning: Could not load spaCy model: {str(e)}")
    print("Document keyword extraction will be limited.")
    # Create a minimal nlp replacement
    class MinimalNLP:
        class Defaults:
            stop_words = set(['der', 'die', 'das', 'den', 'dem', 'des', 'ein', 'eine', 'einer', 'eines', 'einem', 'einen',
                    'und', 'oder', 'aber', 'wenn', 'als', 'an', 'in', 'mit', 'für', 'von', 'zu', 'bei', 'nach',
                    'über', 'unter', 'vor', 'ich', 'du', 'er', 'sie', 'es', 'wir', 'ihr', 'sie'])
        
        def __call__(self, text):
            class Doc:
                def __init__(self, text):
                    self.text = text
                    self.tokens = text.split()
                
                def __iter__(self):
                    for token in self.tokens:
                        yield Token(token)
            
            return Doc(text)
    
    class Token:
        def __init__(self, text):
            self.text = text
            self.pos_ = ""
            self.ent_type_ = ""
            self.is_stop = False
            self.lower_ = text.lower()
    
    nlp = MinimalNLP()

# Set up upload directory
BASE_DIR = Path(os.path.dirname(os.path.abspath(__file__))).parent
UPLOAD_DIR = BASE_DIR / "data" / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True, parents=True)
print(f"Upload directory: {UPLOAD_DIR}")

# Ensure the directory is writable
try:
    test_file = UPLOAD_DIR / ".test_write"
    with open(test_file, "w") as f:
        f.write("test")
    os.remove(test_file)
    print("Upload directory is writable")
except Exception as e:
    print(f"Warning: Upload directory may not be writable: {str(e)}")

class DocumentAnalyzer:
    """Class for analyzing documents and comparing them with projects."""
    
    def __init__(self, project_manager=None):
        """Initialize the document analyzer."""
        self.project_manager = project_manager
        self.documents = {}
        self._load_documents()
    
    def _get_german_stopwords(self) -> List[str]:
        """Get German stopwords for text processing."""
        try:
            return [word for word in nlp.Defaults.stop_words]
        except:
            # Fallback stopwords if spaCy is not available
            return ['der', 'die', 'das', 'den', 'dem', 'des', 'ein', 'eine', 'einer', 'eines', 'einem', 'einen',
                    'und', 'oder', 'aber', 'wenn', 'als', 'an', 'in', 'mit', 'für', 'von', 'zu', 'bei', 'nach',
                    'über', 'unter', 'vor', 'ich', 'du', 'er', 'sie', 'es', 'wir', 'ihr', 'sie']
    
    def _load_documents(self):
        """Load previously uploaded documents."""
        document_index = UPLOAD_DIR / "document_index.json"
        if document_index.exists():
            try:
                self.documents = json.loads(document_index.read_text(encoding="utf-8"))
                print(f"Document index loaded with {len(self.documents)} documents")
            except Exception as e:
                print(f"Error loading document index: {str(e)}")
                self.documents = {}
        else:
            print("No document index found, starting with empty index")
            self.documents = {}
    
    def _save_documents(self):
        """Save document index."""
        document_index = UPLOAD_DIR / "document_index.json"
        try:
            document_index.write_text(json.dumps(self.documents, ensure_ascii=False), encoding="utf-8")
            print(f"Document index saved successfully with {len(self.documents)} documents")
        except Exception as e:
            print(f"Error saving document index: {str(e)}")
            # Try to create an empty index if it doesn't exist
            if not document_index.exists():
                try:
                    document_index.write_text("{}", encoding="utf-8")
                    print("Created empty document index")
                except Exception as e2:
                    print(f"Failed to create empty document index: {str(e2)}")
    
    async def process_document(self, file: UploadFile, document_type: str, name: Optional[str] = None) -> Dict[str, Any]:
        """
        Process an uploaded document.
        
        Args:
            file: The uploaded file
            document_type: Type of document (resume, job_description, etc.)
            name: Optional name for the document
            
        Returns:
            Document metadata
        """
        try:
            if not file.filename.lower().endswith(('.docx', '.doc')):
                raise HTTPException(status_code=400, detail="Only Word documents (.doc, .docx) are supported")
            
            print(f"Processing document: {file.filename}, type: {document_type}")
            
            # Create a unique filename
            timestamp = int(time.time())
            document_id = f"{timestamp}_{os.path.basename(file.filename)}"
            file_path = UPLOAD_DIR / document_id
            
            print(f"Saving file to: {file_path}")
            
            # Save the file
            try:
                content = await file.read()
                with open(file_path, "wb") as f:
                    f.write(content)
                print(f"File saved successfully, size: {len(content)} bytes")
            except Exception as e:
                print(f"Error saving file: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
            
            # Extract text from the document
            try:
                print("Extracting text from document...")
                text = docx2txt.process(str(file_path))
                print(f"Text extracted successfully, length: {len(text)} characters")
                
                # Process text with spaCy for better analysis
                print("Processing text with NLP...")
                doc = nlp(text)
                
                # Extract key information
                print("Extracting keywords...")
                keywords = self._extract_keywords(doc)
            
                # Create document metadata
                document_info = {
                    "id": document_id,
                    "name": name or file.filename,
                    "type": document_type,
                    "path": str(file_path),
                    "size": len(content),
                    "upload_date": str(Path(file_path).stat().st_mtime),
                    "keywords": keywords,
                    "text_length": len(text)
                }
                
                # Save to document index
                self.documents[document_id] = document_info
                self._save_documents()
                
                print(f"Document processed successfully: {document_id}")
                return document_info
            except Exception as e:
                print(f"Error processing document text: {str(e)}")
                # If the file was saved but processing failed, try to clean up
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                        print(f"Cleaned up file after processing error: {file_path}")
                    except:
                        pass
                raise HTTPException(status_code=500, detail=f"Failed to process document: {str(e)}")
        except HTTPException as he:
            # Re-raise HTTP exceptions
            raise he
        except Exception as e:
            print(f"Unexpected error in process_document: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
    
    def _extract_keywords(self, doc) -> List[str]:
        """Extract important keywords from the document."""
        # Extract nouns, proper nouns, and technical terms
        keywords = []
        for token in doc:
            if (token.pos_ in ["NOUN", "PROPN"] or token.ent_type_) and not token.is_stop:
                keywords.append(token.text.lower())
        
        # Count occurrences and get top keywords
        from collections import Counter
        keyword_counts = Counter(keywords)
        return [word for word, count in keyword_counts.most_common(20)]
    
    def get_documents(self) -> List[Dict[str, Any]]:
        """Get list of all uploaded documents."""
        return list(self.documents.values())
    
    def get_document(self, document_id: str) -> Dict[str, Any]:
        """Get a specific document by ID."""
        if document_id not in self.documents:
            raise HTTPException(status_code=404, detail="Document not found")
        return self.documents[document_id]
    
    def delete_document(self, document_id: str) -> Dict[str, Any]:
        """Delete a document."""
        if document_id not in self.documents:
            raise HTTPException(status_code=404, detail="Document not found")
        
        document = self.documents[document_id]
        file_path = Path(document["path"])
        
        # Delete the file
        if file_path.exists():
            file_path.unlink()
        
        # Remove from index
        del self.documents[document_id]
        self._save_documents()
        
        return {"message": f"Document {document_id} deleted successfully"}
    
    def compare_with_projects(self, document_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Compare a document with all projects and return the best matches.
        Uses a simple keyword matching approach instead of TF-IDF.
        
        Args:
            document_id: ID of the document to compare
            limit: Maximum number of matches to return
            
        Returns:
            List of matching projects with similarity scores
        """
        if document_id not in self.documents:
            raise HTTPException(status_code=404, detail="Document not found")
        
        if not self.project_manager:
            raise HTTPException(status_code=500, detail="Project manager not initialized")
        
        # Get document text and keywords
        document = self.documents[document_id]
        document_keywords = set(document.get("keywords", []))
        
        # Get all projects
        all_projects = self.project_manager.get_projects(show_all=True)["projects"]
        
        if not all_projects:
            return []
        
        # Compare document with each project
        try:
            project_matches = []
            
            for project in all_projects:
                # Extract project text
                project_text = f"{project.get('title', '')} {project.get('description', '')}"
                project_skills = project.get('skills', [])
                
                # Calculate simple matching score based on keywords
                matching_keywords = self._get_matching_keywords(document, project)
                keyword_score = len(matching_keywords) / max(len(document_keywords), 1) if document_keywords else 0
                
                # Calculate text similarity based on word overlap
                doc_words = self._extract_words(document["path"])
                project_words = self._extract_words_from_text(project_text)
                
                # Calculate word overlap
                common_words = len(set(doc_words).intersection(set(project_words)))
                total_words = len(set(doc_words).union(set(project_words)))
                text_score = common_words / total_words if total_words > 0 else 0
                
                # Calculate skill match
                skill_score = 0
                if project_skills and document_keywords:
                    skill_matches = sum(1 for skill in project_skills if any(kw.lower() in skill.lower() for kw in document_keywords))
                    skill_score = skill_matches / len(project_skills) if project_skills else 0
                
                # Combined score (weighted average)
                similarity = (0.4 * keyword_score) + (0.4 * text_score) + (0.2 * skill_score)
                
                project_matches.append({
                    "project": project,
                    "similarity": similarity,
                    "matching_keywords": matching_keywords
                })
            
            # Sort by similarity score
            project_matches.sort(key=lambda x: x["similarity"], reverse=True)
            
            # Return top matches
            return project_matches[:limit]
            
        except Exception as e:
            print(f"Error comparing document with projects: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error comparing document: {str(e)}")
    
    def _get_matching_keywords(self, document: Dict[str, Any], project: Dict[str, Any]) -> List[str]:
        """Find matching keywords between document and project."""
        try:
            document_keywords = set(document.get("keywords", []))
            
            # Extract project keywords from title and description
            project_text = f"{project.get('title', '')} {project.get('description', '')}"
            
            # Extract keywords from project text
            project_keywords = set()
            
            try:
                # Try using spaCy if available
                project_doc = nlp(project_text)
                
                for token in project_doc:
                    # Check if token has the required attributes
                    has_pos = hasattr(token, 'pos_')
                    has_ent_type = hasattr(token, 'ent_type_')
                    has_is_stop = hasattr(token, 'is_stop')
                    
                    if ((has_pos and token.pos_ in ["NOUN", "PROPN"]) or 
                        (has_ent_type and token.ent_type_)) and \
                       (not has_is_stop or not token.is_stop):
                        project_keywords.add(token.text.lower())
            except Exception as e:
                print(f"Error extracting keywords with spaCy: {str(e)}")
                # Fallback to simple word extraction
                words = self._extract_words_from_text(project_text)
                project_keywords = set(words)
            
            # Find intersection
            matching = document_keywords.intersection(project_keywords)
            return list(matching)
        except Exception as e:
            print(f"Error in _get_matching_keywords: {str(e)}")
            return []
        
    def _extract_words(self, file_path: str) -> List[str]:
        """Extract words from a document file."""
        try:
            text = docx2txt.process(file_path)
            return self._extract_words_from_text(text)
        except Exception as e:
            print(f"Error extracting words from document: {str(e)}")
            return []
    
    def _extract_words_from_text(self, text: str) -> List[str]:
        """Extract meaningful words from text."""
        # Remove special characters and convert to lowercase
        text = re.sub(r'[^\w\s]', ' ', text.lower())
        
        # Split into words
        words = text.split()
        
        # Remove stopwords
        stopwords = self._get_german_stopwords()
        words = [word for word in words if word not in stopwords and len(word) > 2]
        
        return words
