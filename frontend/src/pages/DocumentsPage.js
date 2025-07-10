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
      
      const response = await fetch('/documents/health', {
        method: 'GET',
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json'
        },
        timeout: 10000 // 10 second timeout
      });
      
      console.log('[DOCUMENTS] Health check response status:', response.status);
      
      if (!response.ok) {
        console.error('[DOCUMENTS] Health check failed with status:', response.status);
        
        // Handle specific error cases for Render deployment
        if (response.status === 404) {
          setError({
            type: 'service_unavailable',
            title: 'Dokument-Service nicht verfügbar',
            message: 'Die Dokument-Funktionalität ist in dieser Bereitstellung nicht aktiviert. Dies ist normal für Cloud-Deployments ohne Dokument-Dependencies.',
            action: 'scraper',
            actionText: 'Zum Scraper'
          });
        } else if (response.status === 500) {
          setError({
            type: 'server_error',
            title: 'Server-Fehler',
            message: 'Der Dokument-Service hat einen internen Fehler. Bitte versuchen Sie es später erneut.',
            action: 'retry',
            actionText: 'Erneut versuchen'
          });
        } else {
          setError({
            type: 'http_error',
            title: 'Verbindungsfehler',
            message: `Dokument-Service antwortet mit Fehlercode ${response.status}. Bitte versuchen Sie es später erneut.`,
            action: 'retry',
            actionText: 'Erneut versuchen'
          });
        }
        return;
      }
      
      // Try to parse response as JSON with better error handling
      let healthData;
      try {
        const responseText = await response.text();
        console.log('[DOCUMENTS] Raw response length:', responseText.length);
        
        if (!responseText.trim()) {
          setError({
            type: 'empty_response',
            title: 'Leere Antwort',
            message: 'Der Dokument-Service hat eine leere Antwort gesendet. Der Service ist möglicherweise nicht richtig initialisiert.',
            action: 'retry',
            actionText: 'Erneut versuchen'
          });
          return;
        }
        
        healthData = JSON.parse(responseText);
        console.log('[DOCUMENTS] Parsed health data:', healthData);
      } catch (parseError) {
        console.error('[DOCUMENTS] JSON parsing error:', parseError);
        setError({
          type: 'invalid_response',
          title: 'Ungültige Antwort',
          message: 'Der Dokument-Service hat eine ungültige Antwort gesendet. Dies deutet auf ein Konfigurationsproblem hin.',
          action: 'scraper',
          actionText: 'Zum Scraper',
          details: `Parse-Fehler: ${parseError.message}`
        });
        return;
      }
      
      // Check if the service is actually healthy
      if (healthData.status !== 'healthy') {
        // Handle different types of unhealthy status
        let errorConfig = {
          type: 'service_unhealthy',
          title: 'Dokument-Service nicht verfügbar',
          action: 'scraper',
          actionText: 'Zum Scraper',
          details: JSON.stringify(healthData, null, 2)
        };
        
        // Check if this is a known dependency issue
        if (healthData.error && healthData.error.includes('document_routes module could not be imported')) {
          errorConfig.type = 'service_unavailable';
          errorConfig.message = 'Die Dokument-Funktionalität ist in dieser Cloud-Bereitstellung nicht aktiviert. Dies ist normal für Render-Deployments ohne Dokument-Dependencies.';
        } else if (healthData.message && healthData.message.includes('dependencies not available')) {
          errorConfig.type = 'dependencies_missing';
          errorConfig.message = 'Die erforderlichen Dokument-Verarbeitungs-Dependencies sind nicht verfügbar. Die Dokument-Funktionalität ist deaktiviert.';
        } else {
          errorConfig.message = healthData.message || 'Der Dokument-Service ist nicht betriebsbereit.';
          errorConfig.action = 'retry';
          errorConfig.actionText = 'Erneut versuchen';
        }
        
        console.log('[DOCUMENTS] Service unhealthy:', healthData);
        setError(errorConfig);
        return;
      }
      
      console.log('[DOCUMENTS] Health check successful, fetching documents...');
      
      // Service is healthy, now fetch documents
      
      console.log('[DOCUMENTS] Health check passed, fetching documents');
      // If health check passes, fetch documents
      await fetchDocuments();
      
    } catch (fetchError) {
      console.error('[DOCUMENTS] Health check network error:', fetchError);
      
      // Handle network errors (common in cloud deployments)
      if (fetchError.name === 'TypeError' && fetchError.message.includes('fetch')) {
        setError({
          type: 'network_error',
          title: 'Netzwerk-Fehler',
          message: 'Verbindung zum Dokument-Service nicht möglich. Dies kann auftreten, wenn der Service in der Cloud-Umgebung nicht verfügbar ist.',
          action: 'scraper',
          actionText: 'Zum Scraper',
          details: fetchError.message
        });
      } else if (fetchError.name === 'AbortError') {
        setError({
          type: 'timeout_error',
          title: 'Zeitüberschreitung',
          message: 'Der Dokument-Service antwortet nicht rechtzeitig. Bitte versuchen Sie es erneut.',
          action: 'retry',
          actionText: 'Erneut versuchen'
        });
      } else {
        setError({
          type: 'unknown_error',
          title: 'Unbekannter Fehler',
          message: 'Ein unbekannter Fehler ist beim Verbinden zum Dokument-Service aufgetreten.',
          action: 'retry',
          actionText: 'Erneut versuchen',
          details: fetchError.message
        });
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
        setError({
          type: 'api_error',
          title: 'API-Fehler',
          message: data.detail || 'Fehler beim Laden der Dokumente',
          action: 'retry',
          actionText: 'Erneut versuchen'
        });
      }
    } catch (err) {
      console.error('[DOCUMENTS] Error fetching documents:', err);
      setError({
        type: 'fetch_error',
        title: 'Verbindungsfehler',
        message: 'Dokumente können nicht geladen werden. Überprüfen Sie Ihre Verbindung.',
        action: 'retry',
        actionText: 'Erneut versuchen',
        details: err.message
      });
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
                    <Alert 
                      severity={error.type === 'service_unavailable' ? 'warning' : 'error'} 
                      sx={{ mb: 2 }}
                    >
                      <Typography variant="h6" gutterBottom>
                        {typeof error === 'string' ? 'Fehler' : error.title || 'Fehler'}
                      </Typography>
                      <Typography variant="body1" gutterBottom>
                        {typeof error === 'string' ? error : error.message}
                      </Typography>
                      
                      {error.details && (
                        <Typography variant="body2" color="text.secondary" sx={{ mt: 1, fontFamily: 'monospace' }}>
                          Details: {error.details}
                        </Typography>
                      )}
                      
                      <Box sx={{ mt: 2, display: 'flex', gap: 1 }}>
                        {error.action === 'retry' && (
                          <Button 
                            variant="outlined"
                            size="small"
                            startIcon={<RefreshIcon />}
                            onClick={checkDocumentHealth}
                          >
                            {error.actionText || 'Erneut versuchen'}
                          </Button>
                        )}
                        
                        {error.action === 'scraper' && (
                          <Button 
                            variant="contained"
                            size="small"
                            onClick={() => window.location.href = '/scraper'}
                          >
                            {error.actionText || 'Zum Scraper'}
                          </Button>
                        )}
                        
                        {/* Always show retry option for structured errors */}
                        {typeof error === 'object' && error.action !== 'retry' && (
                          <Button 
                            variant="outlined"
                            size="small"
                            startIcon={<RefreshIcon />}
                            onClick={checkDocumentHealth}
                          >
                            Nochmal versuchen
                          </Button>
                        )}
                        
                        {/* Fallback for legacy string errors */}
                        {typeof error === 'string' && (
                          <Button 
                            variant="outlined"
                            size="small"
                            startIcon={<RefreshIcon />}
                            onClick={checkDocumentHealth}
                          >
                            Verbindung erneut testen
                          </Button>
                        )}
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
