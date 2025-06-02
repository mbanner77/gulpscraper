import React, { useState, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  Container,
  Grid,
  Typography,
  Box,
  CircularProgress,
  Pagination,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  FormControlLabel,
  Switch,
  Paper,
  Divider,
  Alert,
  Button,
  IconButton,
  Tooltip
} from '@mui/material';
import {
  FilterAlt as FilterIcon,
  Clear as ClearIcon,
  Refresh as RefreshIcon
} from '@mui/icons-material';
import ProjectCard from '../components/ProjectCard';
import { getProjects } from '../services/api';

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
  const [showFilters, setShowFilters] = useState(false);
  
  // Load projects on mount and when filters change
  useEffect(() => {
    const fetchProjects = async () => {
      setLoading(true);
      setError(null);
      
      try {
        // Build query parameters
        const params = {
          page,
          limit: 12,
          search: searchQuery,
          location: location_,
          remote: remoteOnly
        };
        
        const data = await getProjects(params);
        setProjects(data.data);
        setTotalPages(data.totalPages);
        setTotalCount(data.total);
      } catch (err) {
        console.error('Error fetching projects:', err);
        setError('Fehler beim Laden der Projekte. Bitte versuchen Sie es später erneut.');
        setProjects([]);
      } finally {
        setLoading(false);
      }
    };
    
    fetchProjects();
  }, [page, searchQuery, location_, remoteOnly]);
  
  // Update URL when filters change
  useEffect(() => {
    const params = new URLSearchParams();
    if (page > 1) params.set('page', page.toString());
    if (searchQuery) params.set('search', searchQuery);
    if (location_) params.set('location', location_);
    if (remoteOnly) params.set('remote', 'true');
    
    navigate({ search: params.toString() }, { replace: true });
  }, [page, searchQuery, location_, remoteOnly, navigate]);
  
  const handlePageChange = (event, value) => {
    setPage(value);
    window.scrollTo(0, 0);
  };
  
  const handleFilterSubmit = (e) => {
    e.preventDefault();
    // Reset to page 1 when filters change
    setPage(1);
  };
  
  const handleClearFilters = () => {
    setSearchQuery('');
    setLocation('');
    setRemoteOnly(false);
    setPage(1);
  };
  
  const handleFavoriteToggle = () => {
    // This is just to force a re-render when a favorite is toggled
    setProjects([...projects]);
  };

  return (
    <Container maxWidth="xl">
      <Box sx={{ mb: 4 }}>
        <Typography variant="h4" component="h1" gutterBottom>
          GULP Freiberufler-Projekte
        </Typography>
        <Typography variant="subtitle1" color="text.secondary" gutterBottom>
          Durchsuchen Sie die neuesten Projekte für Freiberufler auf GULP.de
        </Typography>
      </Box>
      
      <Paper sx={{ p: 2, mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
          <Typography variant="h6" component="h2">
            Filter
          </Typography>
          <IconButton 
            size="small" 
            onClick={() => setShowFilters(!showFilters)}
            sx={{ ml: 1 }}
          >
            <FilterIcon />
          </IconButton>
          <Box sx={{ flexGrow: 1 }} />
          <Tooltip title="Filter zurücksetzen">
            <IconButton 
              size="small" 
              onClick={handleClearFilters}
              disabled={!searchQuery && !location_ && !remoteOnly}
            >
              <ClearIcon />
            </IconButton>
          </Tooltip>
        </Box>
        
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
                  placeholder="Titel, Beschreibung, Firma..."
                />
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
