import React, { useState, useEffect } from 'react';
import {
  Box,
  Paper,
  Typography,
  CircularProgress,
  Alert,
  Divider,
  Grid,
  Card,
  CardContent,
  CardActions,
  Button,
  Pagination,
  TextField,
  InputAdornment,
  FormControlLabel,
  Checkbox,
  Chip,
  Stack
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import LocationOnIcon from '@mui/icons-material/LocationOn';
import WorkIcon from '@mui/icons-material/Work';
import { getArchivedProjects } from '../services/api';
import { formatDate } from '../utils/dateUtils';

const ProjectArchive = () => {
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalProjects, setTotalProjects] = useState(0);
  const [searchParams, setSearchParams] = useState({
    search: '',
    location: '',
    remote: null,
    limit: 10
  });
  
  useEffect(() => {
    fetchArchivedProjects();
  }, [page, searchParams]);
  
  const fetchArchivedProjects = async () => {
    try {
      setLoading(true);
      
      // Prepare query parameters
      const params = {
        page,
        limit: searchParams.limit,
        ...searchParams.search && { search: searchParams.search },
        ...searchParams.location && { location: searchParams.location },
        ...searchParams.remote !== null && { remote: searchParams.remote }
      };
      
      const data = await getArchivedProjects(params);
      
      setProjects(data.projects || []);
      setTotalProjects(data.total || 0);
      setTotalPages(Math.ceil((data.total || 0) / searchParams.limit));
      setError(null);
    } catch (err) {
      console.error('Fehler beim Laden der archivierten Projekte:', err);
      setError('Die archivierten Projekte konnten nicht geladen werden.');
      setProjects([]);
    } finally {
      setLoading(false);
    }
  };
  
  const handlePageChange = (event, value) => {
    setPage(value);
  };
  
  const handleSearchChange = (event) => {
    const { name, value, checked, type } = event.target;
    
    setSearchParams(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value
    }));
    
    // Reset to first page when search params change
    setPage(1);
  };
  
  const handleRemoteChange = (event) => {
    const { checked } = event.target;
    setSearchParams(prev => ({
      ...prev,
      remote: checked ? true : null
    }));
    setPage(1);
  };
  
  const handleSearch = (event) => {
    event.preventDefault();
    fetchArchivedProjects();
  };
  
  if (loading && projects.length === 0) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', my: 4 }}>
        <CircularProgress />
      </Box>
    );
  }
  
  return (
    <Paper sx={{ p: 3, mb: 4 }}>
      <Typography variant="h6" gutterBottom>
        Projekt-Archiv
      </Typography>
      
      <Typography variant="body2" color="text.secondary" paragraph>
        Hier finden Sie alle Projekte, die älter als 24 Stunden sind.
      </Typography>
      
      <Divider sx={{ my: 2 }} />
      
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}
      
      {/* Search Form */}
      <Paper variant="outlined" sx={{ p: 2, mb: 3 }}>
        <form onSubmit={handleSearch}>
          <Grid container spacing={2} alignItems="center">
            <Grid item xs={12} sm={4}>
              <TextField
                fullWidth
                name="search"
                label="Suche"
                value={searchParams.search}
                onChange={handleSearchChange}
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <SearchIcon />
                    </InputAdornment>
                  ),
                }}
                placeholder="Titel, Beschreibung, Skills..."
              />
            </Grid>
            
            <Grid item xs={12} sm={3}>
              <TextField
                fullWidth
                name="location"
                label="Standort"
                value={searchParams.location}
                onChange={handleSearchChange}
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <LocationOnIcon />
                    </InputAdornment>
                  ),
                }}
                placeholder="Stadt, Region..."
              />
            </Grid>
            
            <Grid item xs={12} sm={3}>
              <FormControlLabel
                control={
                  <Checkbox
                    checked={searchParams.remote === true}
                    onChange={handleRemoteChange}
                    name="remote"
                  />
                }
                label="Remote möglich"
              />
            </Grid>
            
            <Grid item xs={12} sm={2}>
              <Button
                fullWidth
                variant="contained"
                type="submit"
                startIcon={<SearchIcon />}
              >
                Suchen
              </Button>
            </Grid>
          </Grid>
        </form>
      </Paper>
      
      {/* Results Summary */}
      <Box sx={{ mb: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Typography variant="body2" color="text.secondary">
          {totalProjects} Projekte gefunden
        </Typography>
        
        {loading && <CircularProgress size={24} sx={{ ml: 2 }} />}
      </Box>
      
      {/* Project List */}
      {projects.length === 0 ? (
        <Alert severity="info">
          Keine archivierten Projekte gefunden.
        </Alert>
      ) : (
        <Grid container spacing={2}>
          {projects.map((project) => (
            <Grid item xs={12} key={project.id}>
              <Card variant="outlined">
                <CardContent>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 1 }}>
                    <Typography variant="h6" component="div">
                      {project.title}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      Archiviert am: {formatDate(project.created_at || project.updated_at)}
                    </Typography>
                  </Box>
                  
                  <Stack direction="row" spacing={1} sx={{ mb: 2 }}>
                    {project.location && (
                      <Chip 
                        icon={<LocationOnIcon />} 
                        label={project.location} 
                        size="small" 
                        variant="outlined" 
                      />
                    )}
                    {project.companyName && (
                      <Chip 
                        icon={<WorkIcon />} 
                        label={project.companyName} 
                        size="small" 
                        variant="outlined" 
                      />
                    )}
                    {project.isRemoteWorkPossible && (
                      <Chip 
                        label="Remote möglich" 
                        size="small" 
                        color="primary" 
                        variant="outlined" 
                      />
                    )}
                  </Stack>
                  
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                    {project.description?.substring(0, 300)}
                    {project.description?.length > 300 ? '...' : ''}
                  </Typography>
                  
                  {project.skills && typeof project.skills === 'string' && (
                    <Box sx={{ mt: 1 }}>
                      <Typography variant="subtitle2" gutterBottom>
                        Skills:
                      </Typography>
                      <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                        {project.skills.split(',').map((skill, index) => (
                          <Chip 
                            key={index} 
                            label={skill.trim()} 
                            size="small" 
                            sx={{ mb: 1 }} 
                          />
                        ))}
                      </Stack>
                    </Box>
                  )}
                </CardContent>
                <CardActions>
                  <Button 
                    size="small" 
                    href={project.url} 
                    target="_blank" 
                    rel="noopener noreferrer"
                  >
                    Zum Projekt
                  </Button>
                </CardActions>
              </Card>
            </Grid>
          ))}
        </Grid>
      )}
      
      {/* Pagination */}
      {totalPages > 1 && (
        <Box sx={{ display: 'flex', justifyContent: 'center', mt: 3 }}>
          <Pagination 
            count={totalPages} 
            page={page} 
            onChange={handlePageChange} 
            color="primary" 
          />
        </Box>
      )}
    </Paper>
  );
};

export default ProjectArchive;
