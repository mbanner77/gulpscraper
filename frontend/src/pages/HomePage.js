import React, { useState, useEffect, useCallback } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  Container,
  Grid,
  Typography,
  Box,
  CircularProgress,
  Pagination,
  TextField,
  Button,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  FormControlLabel,
  Switch,
  Alert,
  Tooltip,
  InputAdornment,
  FormHelperText,
  IconButton,
  Link,
  Paper
} from '@mui/material';
import {
  FilterAlt as FilterIcon,
  Clear as ClearIcon,
  Refresh as RefreshIcon,
  Archive as ArchiveIcon
} from '@mui/icons-material';
import ProjectCard from '../components/ProjectCard';
import { getProjects, markProjectsAsSeen } from '../services/api';

function HomePage() {
  const location = useLocation();
  const navigate = useNavigate();
  const queryParams = new URLSearchParams(location.search);
  
  // State for projects and pagination
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [page, setPage] = useState(parseInt(queryParams.get('page')) || 1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalCount, setTotalCount] = useState(0);
  
  // State for filters
  const [searchQuery, setSearchQuery] = useState(queryParams.get('search') || '');
  const [location_, setLocation] = useState(queryParams.get('location') || '');
  const [remoteOnly, setRemoteOnly] = useState(queryParams.get('remote') === 'true');
  const [newOnly, setNewOnly] = useState(queryParams.get('new') === 'true');
  // Standardmäßig alle Projekte anzeigen (true), um sicherzustellen, dass Projekte auf Render angezeigt werden
  const [showAllProjects, setShowAllProjects] = useState(queryParams.get('show_all') !== 'false');
  const [showFilters, setShowFilters] = useState(false);
  
  // State for new projects
  const [newProjectIds, setNewProjectIds] = useState([]);
  
  // Funktion zum Laden der Projekte mit useCallback
  const fetchProjects = useCallback(async (forceReprocess = false) => {
    setLoading(true);
    setError(null);
    
    try {
      // Build query parameters
      const params = {
        page,
        limit: 12,
        search: searchQuery,
        location: location_,
        remote: remoteOnly,
        new: newOnly,
        show_all: showAllProjects
      };
      
      // Für Render: force_reprocess Parameter hinzufügen, wenn angefordert
      if (forceReprocess) {
        params.force_reprocess = true;
        console.log('Forcing project reprocessing on fetch');
      }
      
      console.log('Fetching projects with params:', params);
      const data = await getProjects(params);
      console.log('API response:', data);
      console.log('Projects received:', data.projects ? data.projects.length : 0);
      
      // Wenn Projekte vorhanden sind, setzen wir sie und beenden
      if (data.projects && data.projects.length > 0) {
        setProjects(data.projects);
        setTotalProjects(data.total);
        setLoading(false);
        return true; // Erfolgreicher Abruf
      }
      
      console.warn('No projects received from API, trying fallback approaches');
      
      // Wenn wir auf Render sind und keine Projekte erhalten haben, versuchen wir es mit force_reprocess
      const isRender = window.location.hostname.includes('render.com') || 
                      window.location.hostname.includes('onrender.com');
      
      if (isRender && !forceReprocess) {
        console.log('On Render with no projects, retrying with force_reprocess');
        return fetchProjects(true); // Rekursiver Aufruf mit force_reprocess
      }
      
      // Direkter Fallback-API-Aufruf als letzter Versuch
      try {
        // Verwende die gleiche API-URL-Bestimmung wie in api.js
        const apiUrl = (() => {
          console.log('Determining fallback API URL for hostname:', window.location.hostname);
          
          if (process.env.REACT_APP_API_URL) {
            return process.env.REACT_APP_API_URL;
          }
          
          if (isRender) {
            console.log('Detected Render deployment for fallback');
            
            if (window.location.hostname.includes('gulp-job-app')) {
              return window.location.origin.replace('gulp-job-app', 'gulp-job-app-api');
            }
              
              const hostParts = window.location.hostname.split('-');
              if (hostParts.length > 0) {
                const appPrefix = hostParts[0]; // z.B. 'gulp'
                const apiUrl = `https://${appPrefix}-backend.onrender.com`;
                console.log('Using constructed Render API URL with prefix:', apiUrl);
                return apiUrl;
              }
              
              const fallbackUrl = window.location.origin.replace('frontend', 'backend');
              console.log('Using fallback Render API URL:', fallbackUrl);
              return fallbackUrl;
            }
            
            return 'http://localhost:8001';
          })();
          
          console.log('Trying direct fetch from:', apiUrl);
          const directResponse = await fetch(`${apiUrl}/projects?show_all=true&force_reprocess=true`);
          const directData = await directResponse.json();
          console.log('Direct fetch response:', directData);
          
          if (directData.projects && directData.projects.length > 0) {
            console.log('Direct fetch successful, got', directData.projects.length, 'projects');
            setProjects(directData.projects);
            setTotalProjects(directData.total || directData.projects.length);
            return true; // Erfolgreicher direkter Abruf
          } else {
            console.warn('Direct fetch returned no projects');
            // Wenn wir auf Render sind und immer noch keine Projekte haben, versuchen wir es mit einem Seiten-Reload
            if (isRender) {
              console.log('On Render with no projects after all attempts, will try page reload in 5 seconds');
              setTimeout(() => {
                window.location.reload();
              }, 5000);
            }
            setProjects([]);
            setTotalProjects(0);
            setError('Keine Projekte gefunden. Bitte starten Sie den Scraper.');
            return false;
          }
        } catch (directFetchError) {
          console.error('Direct fetch failed:', directFetchError);
          setProjects([]);
          setTotalProjects(0);
          setError('Keine Projekte gefunden. Bitte starten Sie den Scraper.');
          return false;
        }
      } else {
        setProjects(data.projects);
        setTotalProjects(data.total);
        
        // Speichere die IDs der neuen Projekte, um sie hervorzuheben
        if (data.new_project_ids) {
          setNewProjectIds(data.new_project_ids);
        }
        return true;
      }
    } catch (err) {
      console.error('Error fetching projects:', err);
      setError('Fehler beim Laden der Projekte. Bitte versuchen Sie es später erneut.');
      setProjects([]);
      setTotalProjects(0);
      return false;
    } finally {
      setLoading(false);
    }
  }, [page, searchQuery, location_, remoteOnly, newOnly, showAllProjects]);
  
  // Event-Listener für Projekt-Updates (z.B. nach manuellem Scrape)
  useEffect(() => {
    // Handler für das projectsUpdated-Event
    const handleProjectsUpdated = (event) => {
      console.log('Projekte wurden aktualisiert, lade neu...', event?.detail);
      
      // Für Render: Verzögertes Neuladen mit force_reprocess
      const isRender = window.location.hostname.includes('render.com') || 
                      window.location.hostname.includes('onrender.com');
      
      if (isRender) {
        console.log('Render-Umgebung erkannt, verzögertes Laden der Projekte mit force_reprocess');
        // Erste Aktualisierung nach 500ms
        setTimeout(() => {
          console.log('Erste verzögerte Aktualisierung nach Scrape');
          fetchProjects(true); // Mit force_reprocess
          
          // Zweite Aktualisierung nach weiteren 2 Sekunden, falls die erste nicht erfolgreich war
          setTimeout(() => {
            console.log('Zweite verzögerte Aktualisierung nach Scrape');
            fetchProjects(true);
          }, 2000);
        }, 500);
      } else {
        // Für lokale Umgebung: Sofort aktualisieren
        fetchProjects();
      }
    };
    
    // Event-Listener hinzufügen
    window.addEventListener('projectsUpdated', handleProjectsUpdated);
    
    // Für Render: Automatische Aktualisierung alle 5 Sekunden, wenn keine Projekte angezeigt werden
    const isRender = window.location.hostname.includes('render.com') || 
                    window.location.hostname.includes('onrender.com');
    
    let autoRefreshInterval = null;
    
    if (isRender) {
      console.log('Render-Umgebung erkannt, starte Auto-Refresh-Überwachung');
      
      // Starte einen Interval, der prüft, ob Projekte angezeigt werden
      autoRefreshInterval = setInterval(() => {
        // Nur aktualisieren, wenn keine Projekte angezeigt werden und kein Ladevorgang läuft
        if (projects.length === 0 && !loading) {
          console.log('Keine Projekte auf Render gefunden, automatische Aktualisierung...');
          fetchProjects(true); // Mit force_reprocess
        } else if (projects.length > 0) {
          // Wenn Projekte angezeigt werden, stoppe die automatische Aktualisierung
          console.log('Projekte werden angezeigt, stoppe Auto-Refresh');
          clearInterval(autoRefreshInterval);
          autoRefreshInterval = null;
        }
      }, 5000); // Alle 5 Sekunden prüfen
    }
    
    // Cleanup beim Unmount
    return () => {
      window.removeEventListener('projectsUpdated', handleProjectsUpdated);
      if (autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
      }
    };
  }, [fetchProjects, projects, loading]); // Leere Abhängigkeitsliste, damit der Event-Listener nur einmal registriert wird
  
  // Der automatische Neuladen-Mechanismus wurde in den Event-Listener-useEffect integriert
  
  // Load projects on mount and when filters change
  useEffect(() => {
    fetchProjects();
    
    // Update URL with current filters
    const params = new URLSearchParams();
    if (page > 1) params.set('page', page.toString());
    if (searchQuery) params.set('search', searchQuery);
    if (location_) params.set('location', location_);
    if (remoteOnly) params.set('remote', 'true');
    if (newOnly) params.set('new', 'true');
    if (!showAllProjects) params.set('show_all', 'false');
    
    navigate({
      pathname: location.pathname,
      search: params.toString()
    }, { replace: true });
  }, [page, searchQuery, location_, remoteOnly, newOnly, showAllProjects, navigate, location.pathname]);
  
  const handlePageChange = (event, value) => {
    setPage(value);
  };
  
  const handleFilterSubmit = (e) => {
    e.preventDefault();
    setPage(1);  // Reset to first page when applying filters
  };
  
  const handleClearFilters = () => {
    setSearchQuery('');
    setLocation('');
    setRemoteOnly(false);
    setNewOnly(false);
    setPage(1);
  };
  
  const handleFavoriteToggle = () => {
    // Implement favorite toggle functionality
  };
  
  const handleMarkAsSeen = async (projectIds) => {
    try {
      await markProjectsAsSeen(projectIds);
      setNewProjectIds(prev => prev.filter(id => !projectIds.includes(id)));
    } catch (err) {
      console.error('Error marking projects as seen:', err);
    }
  };
  
  return (
    <Container maxWidth="xl" sx={{ py: 4 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4" component="h1" gutterBottom>
          {showAllProjects ? 'Alle GULP Projekte' : 'Aktuelle GULP Projekte'}
        </Typography>
        
        <Box>
          <Button
            variant="outlined"
            startIcon={<FilterIcon />}
            onClick={() => setShowFilters(!showFilters)}
            sx={{ mr: 1 }}
          >
            Filter {showFilters ? 'ausblenden' : 'anzeigen'}
          </Button>
          
          <Button
            variant="outlined"
            color="secondary"
            component={Link}
            href="/scraper"
            startIcon={<ArchiveIcon />}
            sx={{ mr: 1 }}
          >
            Scraper & Archiv
          </Button>
        </Box>
      </Box>
      
      <Paper sx={{ p: 2, mb: 3, display: showFilters ? 'block' : 'none' }}>
        <Typography variant="h6" gutterBottom>
          Projektfilter
        </Typography>
        
        {showFilters && (
          <form onSubmit={handleFilterSubmit}>
            <Grid container spacing={2} alignItems="center">
              <Grid item xs={12} sm={6} md={4}>
                <TextField
                  fullWidth
                  label="Suchbegriff"
                  variant="outlined"
                  size="small"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="z.B. React, Python, DevOps..."
                  InputProps={{
                    endAdornment: searchQuery && (
                      <InputAdornment position="end">
                        <IconButton
                          size="small"
                          onClick={() => setSearchQuery('')}
                        >
                          <ClearIcon fontSize="small" />
                        </IconButton>
                      </InputAdornment>
                    ),
                  }}
                />
                <FormHelperText>
                  Suche in Titel, Beschreibung und Skills
                </FormHelperText>
              </Grid>
              <Grid item xs={12} sm={6} md={4}>
                <TextField
                  fullWidth
                  label="Ort"
                  variant="outlined"
                  size="small"
                  value={location_}
                  onChange={(e) => setLocation(e.target.value)}
                  placeholder="z.B. München, Berlin..."
                />
              </Grid>
              <Grid item xs={12} sm={6} md={4}>
                <FormControlLabel
                  control={
                    <Switch
                      checked={remoteOnly}
                      onChange={(e) => setRemoteOnly(e.target.checked)}
                      color="primary"
                    />
                  }
                  label="Nur Remote-Projekte"
                />
              </Grid>
              <Grid item xs={12} sm={6} md={4}>
                <FormControlLabel
                  control={
                    <Switch
                      checked={newOnly}
                      onChange={(e) => setNewOnly(e.target.checked)}
                      color="primary"
                    />
                  }
                  label="Nur neue Projekte"
                />
              </Grid>
              <Grid item xs={12} sm={6} md={4}>
                <FormControlLabel
                  control={
                    <Switch
                      checked={showAllProjects}
                      onChange={(e) => setShowAllProjects(e.target.checked)}
                      color="primary"
                    />
                  }
                  label="Alle Projekte anzeigen (inkl. Archiv)"
                />
              </Grid>
            </Grid>
          </form>
        )}
      </Paper>
      
      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
          <Button 
            startIcon={<RefreshIcon />}
            onClick={() => window.location.reload()}
            sx={{ ml: 2 }}
          >
            Neu laden
          </Button>
        </Alert>
      )}
      
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="subtitle1">
          {loading ? 'Lade Projekte...' : `${totalCount} Projekte gefunden`}
        </Typography>
      </Box>
      
      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', my: 4 }}>
          <CircularProgress />
        </Box>
      ) : projects.length > 0 ? (
        <>
          <Grid container spacing={3}>
            {projects.map((project) => (
              <Grid item xs={12} sm={6} md={4} lg={3} key={project.id}>
                <ProjectCard 
                  project={project} 
                  onFavoriteToggle={handleFavoriteToggle}
                  isNew={newProjectIds.includes(project.id)}
                  onMarkAsSeen={() => handleMarkAsSeen([project.id])}
                />
              </Grid>
            ))}
          </Grid>
          
          <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
            <Pagination 
              count={totalPages} 
              page={page} 
              onChange={handlePageChange} 
              color="primary" 
              size="large"
              showFirstButton
              showLastButton
            />
          </Box>
        </>
      ) : (
        <Box sx={{ textAlign: 'center', my: 4 }}>
          <Typography variant="h6" color="text.secondary">
            Keine Projekte gefunden
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Versuchen Sie es mit anderen Filterkriterien
          </Typography>
          <Button 
            variant="outlined" 
            color="primary" 
            onClick={handleClearFilters}
            sx={{ mt: 2 }}
          >
            Filter zurücksetzen
          </Button>
        </Box>
      )}
    </Container>
  );
}

export default HomePage;
