import React, { useState, useEffect } from 'react';
import {
  Container,
  Typography,
  Box,
  Grid,
  Paper,
  Button,
  CircularProgress,
  Alert,
  Tabs,
  Tab,
  List,
  ListItem,
  ListItemText,
  ListItemSecondary,
  IconButton,
  Divider,
  Card,
  CardContent,
  CardActions,
  Chip,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem
} from '@mui/material';
import {
  Upload as UploadIcon,
  Delete as DeleteIcon,
  Description as DocumentIcon,
  Compare as CompareIcon,
  Refresh as RefreshIcon
} from '@mui/icons-material';
import { styled } from '@mui/material/styles';
import { getAIConfig } from '../utils/aiConfig';
import ProjectCard from '../components/ProjectCard';

// Styled components for file upload
const VisuallyHiddenInput = styled('input')({
  clip: 'rect(0 0 0 0)',
  clipPath: 'inset(50%)',
  height: 1,
  overflow: 'hidden',
  position: 'absolute',
  bottom: 0,
  left: 0,
  whiteSpace: 'nowrap',
  width: 1,
});

/**
 * Documents page for managing Word documents and comparing with projects
 */
const DocumentsPage = () => {
  // State for document management
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [currentTab, setCurrentTab] = useState(0);
  const [uploadType, setUploadType] = useState('resume');
  const [documentName, setDocumentName] = useState('');
  const [uploadLoading, setUploadLoading] = useState(false);
  const [uploadError, setUploadError] = useState(null);
  const [selectedDocument, setSelectedDocument] = useState(null);
  const [matchingProjects, setMatchingProjects] = useState([]);
  const [compareLoading, setCompareLoading] = useState(false);
  const [compareError, setCompareError] = useState(null);

  // Load documents on component mount
  useEffect(() => {
    checkDocumentHealth();
  }, []);
  
  // Check document service health first
  const checkDocumentHealth = async () => {
    setLoading(true);
    setError(null);
    
    try {
      console.log('[DOCUMENTS] Attempting health check at /documents/health');
      
      const response = await fetch('/documents/health');
      console.log('[DOCUMENTS] Health check response status:', response.status);
      console.log('[DOCUMENTS] Health check response headers:', Object.fromEntries(response.headers.entries()));
      
      if (!response.ok) {
        console.error('[DOCUMENTS] Health check failed with status:', response.status);
        
        // Try to get response text for debugging
        let responseText = '';
        try {
          responseText = await response.text();
          console.log('[DOCUMENTS] Error response body:', responseText.substring(0, 500));
        } catch (e) {
          console.log('[DOCUMENTS] Could not read error response body');
        }
        
        if (response.status === 404) {
          setError('Document routes not found. The document functionality is not available in this deployment.');
        } else if (response.status === 500) {
          setError('Document service internal error. Please check server logs.');
        } else {
          setError(`Document service returned error ${response.status}. Please try again later.`);
        }
        return;
      }
      
      // Try to parse response as JSON with better error handling
      let healthData;
      try {
        const responseText = await response.text();
        console.log('[DOCUMENTS] Raw response:', responseText.substring(0, 500));
        
        if (!responseText.trim()) {
          setError('Document service returned empty response. Service may not be properly initialized.');
          return;
        }
        
        healthData = JSON.parse(responseText);
      } catch (parseError) {
        console.error('[DOCUMENTS] JSON parsing error:', parseError);
        const responsePreview = await response.text().catch(() => 'Could not read response');
        setError(`Document service returned invalid response format. This usually means the document routes are not properly configured on the server. Response preview: ${responsePreview.substring(0, 100)}...`);
        return;
      }
      console.log('[DOCUMENTS] Health check data:', healthData);
      
      if (healthData.status === 'error') {
        setError(`Document service error: ${healthData.error || 'Unknown error'}`);
        return;
      }
      
      if (!healthData.document_analyzer_initialized) {
        setError('Document analyzer not initialized on server. The document processing backend may not be ready.');
        return;
      }
      
      if (!healthData.docx_available) {
        setError('Document processing dependencies not available. Word document support is disabled.');
        return;
      }
      
      console.log('[DOCUMENTS] Health check passed, fetching documents');
      // If health check passes, fetch documents
      await fetchDocuments();
      
    } catch (err) {
      console.error('[DOCUMENTS] Error during health check:', err);
      
      if (err.name === 'TypeError' && err.message.includes('Failed to fetch')) {
        setError('Cannot connect to document service. This could mean: 1) Backend server is not running, 2) Network connection issue, or 3) Document functionality is not available in this deployment.');
      } else {
        setError(`Document service connection failed: ${err.message}. The document functionality may not be available.`);
      }
    } finally {
      setLoading(false);
    }
  };

  // Fetch documents from the API
  const fetchDocuments = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch('/documents/list');
      const data = await response.json();
      
      if (response.ok) {
        setDocuments(data.documents || []);
      } else {
        setError(data.detail || 'Failed to fetch documents');
      }
    } catch (err) {
      console.error('Error fetching documents:', err);
      setError('Failed to connect to the server');
    } finally {
      setLoading(false);
    }
  };

  // Handle document upload
  const handleFileUpload = async (event) => {
    const file = event.target.files[0];
    if (!file) return;
    
    // Validate file type
    if (!file.name.toLowerCase().endsWith('.docx') && !file.name.toLowerCase().endsWith('.doc')) {
      setUploadError('Only Word documents (.doc, .docx) are supported');
      return;
    }
    
    setUploadLoading(true);
    setUploadError(null);
    
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('document_type', uploadType);
      
      if (documentName.trim()) {
        formData.append('name', documentName);
      }
      
      const response = await fetch('/documents/upload', {
        method: 'POST',
        body: formData,
      });
      
      const data = await response.json();
      
      if (response.ok) {
        // Add the new document to the list
        setDocuments(prev => [...prev, data]);
        setDocumentName('');
        setUploadType('resume');
      } else {
        setUploadError(data.detail || 'Failed to upload document');
      }
    } catch (err) {
      console.error('Error uploading document:', err);
      setUploadError('Failed to upload document');
    } finally {
      setUploadLoading(false);
    }
  };

  // Handle document deletion
  const handleDeleteDocument = async (documentId) => {
    if (!window.confirm('Are you sure you want to delete this document?')) {
      return;
    }
    
    try {
      const response = await fetch(`/documents/${documentId}`, {
        method: 'DELETE',
      });
      
      if (response.ok) {
        // Remove the document from the list
        setDocuments(prev => prev.filter(doc => doc.id !== documentId));
        
        // If the deleted document was selected, clear the selection
        if (selectedDocument && selectedDocument.id === documentId) {
          setSelectedDocument(null);
          setMatchingProjects([]);
        }
      } else {
        const data = await response.json();
        alert(data.detail || 'Failed to delete document');
      }
    } catch (err) {
      console.error('Error deleting document:', err);
      alert('Failed to delete document');
    }
  };

  // Handle document comparison with projects
  const handleCompareDocument = async (document) => {
    setSelectedDocument(document);
    setCompareLoading(true);
    setCompareError(null);
    setMatchingProjects([]);
    
    try {
      const response = await fetch(`/documents/${document.id}/compare`);
      const data = await response.json();
      
      if (response.ok) {
        setMatchingProjects(data.matches || []);
        setCurrentTab(1); // Switch to matches tab
      } else {
        setCompareError(data.detail || 'Failed to compare document');
      }
    } catch (err) {
      console.error('Error comparing document:', err);
      setCompareError('Failed to compare document with projects');
    } finally {
      setCompareLoading(false);
    }
  };

  // Handle tab change
  const handleTabChange = (event, newValue) => {
    setCurrentTab(newValue);
  };

  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
      <Typography variant="h4" gutterBottom>
        Dokument-Analyse
      </Typography>
      
      <Typography variant="body1" paragraph>
        Laden Sie Word-Dokumente (Lebenslauf, Stellenbeschreibungen) hoch und vergleichen Sie diese mit gefundenen Projekten.
        Die KI-Analyse hilft Ihnen, die am besten passenden Projekte zu finden.
      </Typography>
      
      <Grid container spacing={3}>
        <Grid item xs={12}>
          <Paper sx={{ p: 3, mb: 3 }}>
            <Typography variant="h6" gutterBottom>
              Dokument hochladen
            </Typography>
            
            <Grid container spacing={2} alignItems="center">
              <Grid item xs={12} sm={4}>
                <TextField
                  fullWidth
                  label="Dokumentname (optional)"
                  value={documentName}
                  onChange={(e) => setDocumentName(e.target.value)}
                  size="small"
                  placeholder="z.B. Mein Lebenslauf 2025"
                />
              </Grid>
              
              <Grid item xs={12} sm={4}>
                <FormControl fullWidth size="small">
                  <InputLabel>Dokumenttyp</InputLabel>
                  <Select
                    value={uploadType}
                    onChange={(e) => setUploadType(e.target.value)}
                    label="Dokumenttyp"
                  >
                    <MenuItem value="resume">Lebenslauf</MenuItem>
                    <MenuItem value="job_description">Stellenbeschreibung</MenuItem>
                    <MenuItem value="skills">Skillprofil</MenuItem>
                    <MenuItem value="other">Sonstiges</MenuItem>
                  </Select>
                </FormControl>
              </Grid>
              
              <Grid item xs={12} sm={4}>
                <Button
                  component="label"
                  variant="contained"
                  startIcon={<UploadIcon />}
                  disabled={uploadLoading}
                  fullWidth
                >
                  {uploadLoading ? <CircularProgress size={24} /> : 'Word-Datei auswählen'}
                  <VisuallyHiddenInput type="file" onChange={handleFileUpload} accept=".doc,.docx" />
                </Button>
              </Grid>
            </Grid>
            
            {uploadError && (
              <Alert severity="error" sx={{ mt: 2 }}>
                {uploadError}
              </Alert>
            )}
          </Paper>
        </Grid>
        
        <Grid item xs={12}>
          <Paper sx={{ width: '100%' }}>
            <Tabs
              value={currentTab}
              onChange={handleTabChange}
              indicatorColor="primary"
              textColor="primary"
              variant="fullWidth"
            >
              <Tab label="Meine Dokumente" />
              <Tab label="Passende Projekte" disabled={!selectedDocument} />
            </Tabs>
            
            <Box sx={{ p: 3 }}>
              {currentTab === 0 && (
                <>
                  {loading ? (
                    <Box sx={{ display: 'flex', justifyContent: 'center', my: 4 }}>
                      <CircularProgress />
                    </Box>
                  ) : error ? (
                    <Alert severity="error" sx={{ mb: 2 }}>
                      <Typography variant="body1" gutterBottom>
                        {error}
                      </Typography>
                      <Box sx={{ mt: 1 }}>
                        <Button 
                          variant="outlined"
                          size="small"
                          startIcon={<RefreshIcon />}
                          onClick={checkDocumentHealth}
                        >
                          Verbindung erneut testen
                        </Button>
                      </Box>
                    </Alert>
                  ) : documents.length > 0 ? (
                    <Grid container spacing={2}>
                      {documents.map((document) => (
                        <Grid item xs={12} sm={6} md={4} key={document.id}>
                          <Card variant="outlined">
                            <CardContent>
                              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                                <DocumentIcon sx={{ mr: 1 }} />
                                <Typography variant="h6" noWrap>
                                  {document.name}
                                </Typography>
                              </Box>
                              
                              <Typography variant="body2" color="text.secondary">
                                Typ: {document.type === 'resume' ? 'Lebenslauf' : 
                                     document.type === 'job_description' ? 'Stellenbeschreibung' : 
                                     document.type === 'skills' ? 'Skillprofil' : 'Sonstiges'}
                              </Typography>
                              
                              <Typography variant="body2" color="text.secondary">
                                Größe: {Math.round(document.size / 1024)} KB
                              </Typography>
                              
                              <Box sx={{ mt: 2 }}>
                                <Typography variant="caption" color="text.secondary">
                                  Keywords:
                                </Typography>
                                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mt: 0.5 }}>
                                  {document.keywords.slice(0, 5).map((keyword, index) => (
                                    <Chip key={index} label={keyword} size="small" />
                                  ))}
                                  {document.keywords.length > 5 && (
                                    <Chip label={`+${document.keywords.length - 5}`} size="small" variant="outlined" />
                                  )}
                                </Box>
                              </Box>
                            </CardContent>
                            
                            <CardActions>
                              <Button 
                                size="small" 
                                startIcon={<CompareIcon />}
                                onClick={() => handleCompareDocument(document)}
                              >
                                Mit Projekten vergleichen
                              </Button>
                              <IconButton 
                                size="small" 
                                color="error"
                                onClick={() => handleDeleteDocument(document.id)}
                              >
                                <DeleteIcon />
                              </IconButton>
                            </CardActions>
                          </Card>
                        </Grid>
                      ))}
                    </Grid>
                  ) : (
                    <Box sx={{ textAlign: 'center', my: 4 }}>
                      <Typography variant="h6" color="text.secondary">
                        Keine Dokumente vorhanden
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        Laden Sie Word-Dokumente hoch, um sie mit Projekten zu vergleichen
                      </Typography>
                    </Box>
                  )}
                </>
              )}
              
              {currentTab === 1 && selectedDocument && (
                <>
                  <Box sx={{ mb: 3 }}>
                    <Typography variant="h6" gutterBottom>
                      Analyse für: {selectedDocument.name}
                    </Typography>
                    
                    {compareLoading ? (
                      <Box sx={{ display: 'flex', justifyContent: 'center', my: 4 }}>
                        <CircularProgress />
                      </Box>
                    ) : compareError ? (
                      <Alert severity="error" sx={{ mb: 2 }}>
                        {compareError}
                      </Alert>
                    ) : matchingProjects.length > 0 ? (
                      <>
                        <Typography variant="body2" paragraph>
                          Die folgenden Projekte passen am besten zu Ihrem Dokument:
                        </Typography>
                        
                        <Grid container spacing={3}>
                          {matchingProjects.map((match, index) => (
                            <Grid item xs={12} key={index}>
                              <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
                                <Box sx={{ mb: 2 }}>
                                  <Typography variant="subtitle1" gutterBottom>
                                    Übereinstimmung: {Math.round(match.similarity * 100)}%
                                  </Typography>
                                  
                                  {match.matching_keywords?.length > 0 && (
                                    <Box>
                                      <Typography variant="caption" color="text.secondary">
                                        Übereinstimmende Keywords:
                                      </Typography>
                                      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mt: 0.5 }}>
                                        {match.matching_keywords.map((keyword, idx) => (
                                          <Chip key={idx} label={keyword} size="small" color="primary" variant="outlined" />
                                        ))}
                                      </Box>
                                    </Box>
                                  )}
                                </Box>
                                
                                <ProjectCard project={match.project} />
                              </Paper>
                            </Grid>
                          ))}
                        </Grid>
                      </>
                    ) : (
                      <Box sx={{ textAlign: 'center', my: 4 }}>
                        <Typography variant="h6" color="text.secondary">
                          Keine passenden Projekte gefunden
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          Versuchen Sie es mit einem anderen Dokument oder warten Sie, bis neue Projekte verfügbar sind
                        </Typography>
                      </Box>
                    )}
                  </Box>
                </>
              )}
            </Box>
          </Paper>
        </Grid>
      </Grid>
    </Container>
  );
};

export default DocumentsPage;
