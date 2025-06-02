import React, { useState, useEffect } from 'react';
import {
  Container,
  Typography,
  Box,
  Grid,
  Button,
  Alert,
  Divider,
  Paper
} from '@mui/material';
import { Delete as DeleteIcon } from '@mui/icons-material';
import ProjectCard from '../components/ProjectCard';
import { favoritesManager } from '../services/api';

function FavoritesPage() {
  const [favorites, setFavorites] = useState([]);
  
  useEffect(() => {
    // Load favorites from localStorage
    setFavorites(favoritesManager.getFavorites());
  }, []);
  
  const handleFavoriteToggle = (projectId, isFavorite) => {
    if (!isFavorite) {
      // Update the state when a project is removed from favorites
      setFavorites(favorites.filter(project => project.id !== projectId));
    }
  };
  
  const handleClearAllFavorites = () => {
    if (window.confirm('Möchten Sie wirklich alle Favoriten löschen?')) {
      // Clear all favorites in localStorage
      localStorage.removeItem('favorites');
      setFavorites([]);
    }
  };

  return (
    <Container maxWidth="xl">
      <Box sx={{ mb: 4 }}>
        <Typography variant="h4" component="h1" gutterBottom>
          Meine Favoriten
        </Typography>
        <Typography variant="subtitle1" color="text.secondary" gutterBottom>
          Ihre gespeicherten Projekte
        </Typography>
      </Box>
      
      {favorites.length > 0 ? (
        <>
          <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 3 }}>
            <Button 
              variant="outlined" 
              color="error" 
              startIcon={<DeleteIcon />}
              onClick={handleClearAllFavorites}
            >
              Alle Favoriten löschen
            </Button>
          </Box>
          
          <Grid container spacing={3}>
            {favorites.map((project) => (
              <Grid item xs={12} sm={6} md={4} lg={3} key={project.id}>
                <ProjectCard 
                  project={project} 
                  onFavoriteToggle={handleFavoriteToggle}
                />
              </Grid>
            ))}
          </Grid>
        </>
      ) : (
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <Alert severity="info" sx={{ mb: 3 }}>
            Sie haben noch keine Projekte zu Ihren Favoriten hinzugefügt.
          </Alert>
          <Typography variant="body1" paragraph>
            Durchsuchen Sie die Projekte und klicken Sie auf das Herz-Symbol, um ein Projekt zu Ihren Favoriten hinzuzufügen.
          </Typography>
          <Button 
            variant="contained" 
            color="primary" 
            href="/"
          >
            Projekte durchsuchen
          </Button>
        </Paper>
      )}
    </Container>
  );
}

export default FavoritesPage;
