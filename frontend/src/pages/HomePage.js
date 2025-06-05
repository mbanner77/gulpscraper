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
  const fetchProjects = useCallback(async () => {
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
      
      console.log('Fetching projects with params:', params);
      const data = await getProjects(params);
      console.log('API response:', data);
      console.log('Projects received:', data.projects ? data.projects.length : 0);
      
      if (!data.projects || data.projects.length === 0) {
        console.warn('No projects received from API');
        // Try a direct fetch to debug using the same API URL from api.js
        try {
          // Verwende die gleiche API-URL-Bestimmung wie in api.js
          const apiUrl = (() => {
            console.log('Determining fallback API URL for hostname:', window.location.hostname);
            
            if (process.env.REACT_APP_API_URL) {
              return process.env.REACT_APP_API_URL;
            }
            
            if (window.location.hostname.includes('render.com') || 
                window.location.hostname.includes('onrender.com')) {
              console.log('Detected Render deployment for fallback');
              
              if (window.location.hostname.includes('gulp-job-app')) {
                return window.location.origin.replace('gulp-job-app', 'gulp-job-app-api');
              }
              
              const hostParts = window.location.hostname.split('-');
              if (hostParts.length > 0) {
                const appPrefix = hostParts[0];
                return `https://${appPrefix}-backend.onrender.com`;
              }
              
              return window.location.origin.replace('frontend', 'backend');
            }
            
            return 'http://localhost:8001';
          })();
          
          console.log('Trying direct fetch from:', apiUrl);
          const directResponse = await fetch(`${apiUrl}/projects?${new URLSearchParams(params)}`);
          const directData = await directResponse.json();
          console.log('Direct fetch response:', directData);
          
          if (directData.projects && directData.projects.length > 0) {
            setProjects(directData.projects);
            setTotalCount(directData.total || directData.projects.length);
            setTotalPages(Math.ceil((directData.total || directData.projects.length) / 12));
            setNewProjectIds(directData.new_project_ids || []);
          } else {
            setError('Keine Projekte gefunden. Bitte versuchen Sie es später erneut.');
          }
        } catch (directErr) {
          console.error('Direct fetch failed:', directErr);
          setError('Fehler beim Laden der Projekte. Bitte versuchen Sie es später erneut.');
        }
      } else {
        setProjects(data.projects);
        setTotalCount(data.total || data.projects.length);
        setTotalPages(Math.ceil((data.total || data.projects.length) / 12));
        setNewProjectIds(data.new_project_ids || []);
      }
    } catch (err) {
      console.error('Error fetching projects:', err);
      setError('Fehler beim Laden der Projekte. Bitte versuchen Sie es später erneut.');
    } finally {
      setLoading(false);
    }
  }, [page, searchQuery, location_, remoteOnly, newOnly, showAllProjects]);
  
  // Event-Listener für Projekt-Updates (z.B. nach manuellem Scrape)
  useEffect(() => {
    // Handler für das projectsUpdated-Event
    const handleProjectsUpdated = (event) => {
      console.log('Projekte wurden aktualisiert, lade neu...', event?.detail);
      
      // Für Render: Verzögertes Neuladen, um sicherzustellen, dass die Daten verfügbar sind
      if (window.location.hostname.includes('render.com') || 
          window.location.hostname.includes('onrender.com')) {
        console.log('Render-Umgebung erkannt, verzögertes Laden der Projekte');
        setTimeout(() => {
          fetchProjects();
        }, 500);
      } else {
        fetchProjects();
      }
    };
    
    // Event-Listener hinzufügen
    window.addEventListener('projectsUpdated', handleProjectsUpdated);
    
    // Event-Listener entfernen beim Aufräumen
    return () => {
      window.removeEventListener('projectsUpdated', handleProjectsUpdated);
    };
  }, []); // Leere Abhängigkeitsliste, damit der Event-Listener nur einmal registriert wird
  
  // Automatisches Neuladen der Projekte alle 5 Sekunden, wenn keine Projekte angezeigt werden und wir auf Render sind
  useEffect(() => {
    // Nur auf Render und nur wenn keine Projekte angezeigt werden
    if ((window.location.hostname.includes('render.com') || 
         window.location.hostname.includes('onrender.com')) && 
        projects.length === 0 && !loading) {
      
      console.log('Keine Projekte auf Render, starte automatisches Neuladen...');
      
      const intervalId = setInterval(() => {
        console.log('Automatisches Neuladen der Projekte...');
        fetchProjects();
      }, 5000); // Alle 5 Sekunden
      
      return () => clearInterval(intervalId);
    }
  }, [projects.length, loading, fetchProjects]);
  
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
