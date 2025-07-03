import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Container,
  Typography,
  Box,
  Paper,
  Grid,
  Button,
  Chip,
  Divider,
  CircularProgress,
  Alert,
  IconButton,
  Card,
  CardMedia
} from '@mui/material';
import {
  ArrowBack as ArrowBackIcon,
  Favorite as FavoriteIcon,
  FavoriteBorder as FavoriteBorderIcon,
  LocationOn as LocationIcon,
  CalendarToday as CalendarIcon,
  AccessTime as AccessTimeIcon,
  Laptop as LaptopIcon,
  OpenInNew as OpenInNewIcon
} from '@mui/icons-material';
import { getProjectById, favoritesManager } from '../services/api';

function ProjectDetailsPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  
  const [project, setProject] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isFavorite, setIsFavorite] = useState(false);
  
  useEffect(() => {
    const fetchProject = async () => {
      setLoading(true);
      setError(null);
      
      try {
        // First check if it's in favorites
        const favorites = favoritesManager.getFavorites();
        const favoriteProject = favorites.find(p => p.id === id);
        
        if (favoriteProject) {
          setProject(favoriteProject);
          setIsFavorite(true);
        } else {
          // If not in favorites, fetch from API
          const data = await getProjectById(id);
          setProject(data);
          setIsFavorite(favoritesManager.isFavorite(id));
        }
      } catch (err) {
        console.error(`Error fetching project with ID ${id}:`, err);
        
        // Extract more detailed error information
        let errorMessage = 'Fehler beim Laden des Projekts. Bitte versuchen Sie es später erneut.';
        
        if (err.response) {
          // API responded with an error status
          const status = err.response.status;
          const data = err.response.data;
          
          if (status === 404) {
            if (data?.error?.includes('No project data available')) {
              errorMessage = 'Noch keine Projektdaten verfügbar. Bitte führen Sie zunächst einen Scraper-Lauf durch.';
            } else if (data?.error?.includes('not found')) {
              errorMessage = `Projekt mit ID ${id} wurde nicht gefunden. Möglicherweise wurde es noch nicht gescrapt oder die ID ist ungültig.`;
            } else {
              errorMessage = 'Projekt nicht gefunden.';
            }
          } else if (status === 500) {
            if (data?.error?.includes('JSON')) {
              errorMessage = 'Fehler beim Laden der Projektdaten. Die Datenbank könnte beschädigt sein.';
            } else {
              errorMessage = `Server-Fehler: ${data?.error || 'Unbekannter Fehler'}`;
            }
          } else {
            errorMessage = `HTTP-Fehler ${status}: ${data?.error || err.message}`;
          }
        } else if (err.request) {
          // Network error
          errorMessage = 'Netzwerkfehler: Keine Verbindung zum Server möglich. Bitte überprüfen Sie Ihre Internetverbindung.';
        } else {
          // Other error
          errorMessage = `Unerwarteter Fehler: ${err.message}`;
        }
        
        // Log detailed error info for debugging
        console.error('Detailed error info:', {
          projectId: id,
          error: err,
          status: err.response?.status,
          statusText: err.response?.statusText,
          data: err.response?.data,
          url: err.config?.url,
          method: err.config?.method
        });
        
        setError(errorMessage);
      } finally {
        setLoading(false);
      }
    };
    
    fetchProject();
  }, [id]);
  
  const handleFavoriteToggle = () => {
    if (isFavorite) {
      favoritesManager.removeFavorite(id);
    } else if (project) {
      favoritesManager.addFavorite(project);
    }
    setIsFavorite(!isFavorite);
  };
  
  const formatDate = (dateString) => {
    if (!dateString) return 'Nicht angegeben';
    const date = new Date(dateString);
    return date.toLocaleDateString('de-DE', {
      year: 'numeric',
      month: 'long',
      day: 'numeric'
    });
  };
  
  if (loading) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '50vh' }}>
          <CircularProgress />
        </Box>
      </Container>
    );
  }
  
  if (error || !project) {
    const isNoDataError = error && error.includes('Noch keine Projektdaten verfügbar');
    const isNotFoundError = error && error.includes('wurde nicht gefunden');
    const isNetworkError = error && error.includes('Netzwerkfehler');
    
    return (
      <Container maxWidth="lg">
        <Box sx={{ my: 4 }}>
          <Button 
            startIcon={<ArrowBackIcon />} 
            onClick={() => navigate(-1)}
            sx={{ mb: 2 }}
          >
            Zurück
          </Button>
          
          <Alert 
            severity={isNetworkError ? "warning" : "error"} 
            sx={{ mb: 3 }}
            action={
              isNoDataError ? (
                <Button 
                  color="inherit" 
                  size="small" 
                  onClick={() => navigate('/scraper')}
                >
                  Zum Scraper
                </Button>
              ) : isNotFoundError ? (
                <Button 
                  color="inherit" 
                  size="small" 
                  onClick={() => navigate('/')}
                >
                  Alle Projekte
                </Button>
              ) : isNetworkError ? (
                <Button 
                  color="inherit" 
                  size="small" 
                  onClick={() => window.location.reload()}
                >
                  Erneut versuchen
                </Button>
              ) : null
            }
          >
            {error || 'Projekt nicht gefunden'}
            
            {isNoDataError && (
              <Box sx={{ mt: 2, fontSize: '0.875rem' }}>
                <strong>Hinweis:</strong> Starten Sie einen Scraper-Lauf, um aktuelle Projektdaten zu laden.
              </Box>
            )}
            
            {isNotFoundError && (
              <Box sx={{ mt: 2, fontSize: '0.875rem' }}>
                <strong>Projekt-ID:</strong> {id}<br/>
                <strong>Tipp:</strong> Überprüfen Sie die URL oder kehren Sie zur Projektübersicht zurück.
              </Box>
            )}
            
            {isNetworkError && (
              <Box sx={{ mt: 2, fontSize: '0.875rem' }}>
                <strong>Mögliche Lösungen:</strong>
                <ul style={{ margin: '8px 0', paddingLeft: '20px' }}>
                  <li>Internetverbindung prüfen</li>
                  <li>Seite neu laden</li>
                  <li>Später erneut versuchen</li>
                </ul>
              </Box>
            )}
          </Alert>
          
          {process.env.NODE_ENV === 'development' && (
            <Alert severity="info" sx={{ mt: 2 }}>
              <Typography variant="subtitle2" gutterBottom>
                Debug-Informationen (nur in Entwicklung sichtbar):
              </Typography>
              <Typography variant="body2" component="pre" sx={{ fontSize: '0.75rem', fontFamily: 'monospace' }}>
                Projekt-ID: {id}{"\n"}
                Error: {error}{"\n"}
                Zeitstempel: {new Date().toISOString()}
              </Typography>
            </Alert>
          )}
        </Box>
      </Container>
    );
  }

  return (
    <Container maxWidth="lg">
      <Box sx={{ my: 4 }}>
        <Button 
          startIcon={<ArrowBackIcon />} 
          onClick={() => navigate(-1)}
          sx={{ mb: 2 }}
        >
          Zurück zur Übersicht
        </Button>
        
        <Paper sx={{ p: 3, mb: 4 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
            <Typography variant="h4" component="h1" gutterBottom>
              {project.title}
            </Typography>
            
            <IconButton 
              color={isFavorite ? "secondary" : "default"} 
              onClick={handleFavoriteToggle}
              size="large"
              sx={{ ml: 2 }}
            >
              {isFavorite ? <FavoriteIcon /> : <FavoriteBorderIcon />}
            </IconButton>
          </Box>
          
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 3 }}>
            {project.location && (
              <Chip 
                icon={<LocationIcon />} 
                label={project.location} 
                variant="outlined"
              />
            )}
            
            {project.isRemoteWorkPossible && (
              <Chip 
                icon={<LaptopIcon />} 
                label="Remote möglich" 
                color="primary" 
                variant="outlined"
              />
            )}
            
            {project.startDate && (
              <Chip 
                icon={<AccessTimeIcon />} 
                label={`Start: ${project.startDate}`} 
                variant="outlined"
              />
            )}
            
            {project.originalPublicationDate && (
              <Chip 
                icon={<CalendarIcon />} 
                label={`Veröffentlicht: ${formatDate(project.originalPublicationDate)}`} 
                variant="outlined"
              />
            )}
          </Box>
          
          <Grid container spacing={4}>
            <Grid item xs={12} md={8}>
              <Typography variant="h6" gutterBottom>
                Projektbeschreibung
              </Typography>
              
              <Typography variant="body1" paragraph sx={{ whiteSpace: 'pre-line' }}>
                {project.description || 'Keine Beschreibung vorhanden'}
              </Typography>
              
              {project.skills && project.skills.length > 0 && (
                <>
                  <Typography variant="h6" gutterBottom sx={{ mt: 3 }}>
                    Skills
                  </Typography>
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                    {project.skills.map((skill, index) => (
                      <Chip 
                        key={index} 
                        label={skill} 
                        size="small"
                        color="primary"
                      />
                    ))}
                  </Box>
                </>
              )}
              
              {project.url && (
                <Button 
                  variant="contained" 
                  color="primary"
                  startIcon={<OpenInNewIcon />}
                  href={project.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  sx={{ mt: 4 }}
                >
                  Auf GULP.de ansehen
                </Button>
              )}
            </Grid>
            
            <Grid item xs={12} md={4}>
              <Card sx={{ mb: 3 }}>
                <CardMedia
                  component="img"
                  height="100"
                  image={project.companyLogoUrl || 'https://via.placeholder.com/300x100?text=Kein+Logo'}
                  alt={project.companyName || 'Firmenlogo'}
                  sx={{ 
                    objectFit: 'contain', 
                    backgroundColor: '#f5f5f5', 
                    p: 2 
                  }}
                />
                <Box sx={{ p: 2 }}>
                  <Typography variant="h6" gutterBottom>
                    {project.companyName || 'Unbekanntes Unternehmen'}
                  </Typography>
                  
                  <Divider sx={{ my: 2 }} />
                  
                  <Typography variant="subtitle2" gutterBottom>
                    Projektdetails
                  </Typography>
                  
                  <Grid container spacing={1}>
                    <Grid item xs={4}>
                      <Typography variant="body2" color="text.secondary">
                        Typ:
                      </Typography>
                    </Grid>
                    <Grid item xs={8}>
                      <Typography variant="body2">
                        {project.type === 'EXTERNAL' ? 'Externes Projekt' : project.type || 'Nicht angegeben'}
                      </Typography>
                    </Grid>
                    
                    <Grid item xs={4}>
                      <Typography variant="body2" color="text.secondary">
                        Start:
                      </Typography>
                    </Grid>
                    <Grid item xs={8}>
                      <Typography variant="body2">
                        {project.startDate || 'Nicht angegeben'}
                      </Typography>
                    </Grid>
                    
                    <Grid item xs={4}>
                      <Typography variant="body2" color="text.secondary">
                        Dauer:
                      </Typography>
                    </Grid>
                    <Grid item xs={8}>
                      <Typography variant="body2">
                        {project.duration || 'Nicht angegeben'}
                      </Typography>
                    </Grid>
                    
                    <Grid item xs={4}>
                      <Typography variant="body2" color="text.secondary">
                        Remote:
                      </Typography>
                    </Grid>
                    <Grid item xs={8}>
                      <Typography variant="body2">
                        {project.isRemoteWorkPossible ? 'Ja' : 'Nicht angegeben'}
                      </Typography>
                    </Grid>
                    
                    <Grid item xs={4}>
                      <Typography variant="body2" color="text.secondary">
                        ID:
                      </Typography>
                    </Grid>
                    <Grid item xs={8}>
                      <Typography variant="body2" sx={{ wordBreak: 'break-all' }}>
                        {project.id}
                      </Typography>
                    </Grid>
                  </Grid>
                </Box>
              </Card>
            </Grid>
          </Grid>
        </Paper>
      </Box>
    </Container>
  );
}

export default ProjectDetailsPage;
