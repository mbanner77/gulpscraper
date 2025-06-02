import React, { useState, useEffect } from 'react';
import { 
  Container, 
  Typography, 
  Box, 
  Button, 
  Paper, 
  CircularProgress,
  Alert,
  TextField,
  Divider,
  Grid,
  Card,
  CardContent,
  List,
  ListItem,
  ListItemText
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import { triggerScrape, getScraperStatus } from '../services/api';

const ScraperPage = () => {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [pages, setPages] = useState('1-3');
  const [refreshInterval, setRefreshInterval] = useState(null);

  const fetchStatus = async () => {
    try {
      setLoading(true);
      const statusData = await getScraperStatus();
      setStatus(statusData);
      setError(null);
    } catch (err) {
      setError('Failed to fetch scraper status. Please try again later.');
      console.error('Error fetching status:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
    
    // Set up auto-refresh if scraping is in progress
    return () => {
      if (refreshInterval) {
        clearInterval(refreshInterval);
      }
    };
  }, []);

  useEffect(() => {
    // If scraping is in progress, set up auto-refresh
    if (status?.is_scraping) {
      const interval = setInterval(fetchStatus, 5000);
      setRefreshInterval(interval);
      return () => clearInterval(interval);
    } else if (refreshInterval) {
      clearInterval(refreshInterval);
      setRefreshInterval(null);
    }
  }, [status?.is_scraping]);

  const handleRefresh = () => {
    fetchStatus();
  };

  const handleStartScrape = async () => {
    try {
      setLoading(true);
      
      // Parse page range
      let pagesList = null;
      if (pages && pages.trim() !== '') {
        if (pages.includes('-')) {
          const [start, end] = pages.split('-').map(p => parseInt(p.trim()));
          pagesList = Array.from({ length: end - start + 1 }, (_, i) => i + start);
        } else {
          pagesList = pages.split(',').map(p => parseInt(p.trim()));
        }
      }
      
      const result = await triggerScrape(pagesList);
      setSuccess('Scrape started successfully! The status will update automatically.');
      
      // Auto-refresh status after starting a scrape
      setTimeout(fetchStatus, 1000);
      
      // Clear success message after 5 seconds
      setTimeout(() => setSuccess(null), 5000);
    } catch (err) {
      setError('Failed to start scrape. Please try again later.');
      console.error('Error starting scrape:', err);
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'Never';
    return new Date(dateString).toLocaleString();
  };

  return (
    <Container maxWidth="md" sx={{ mt: 4, mb: 4 }}>
      <Typography variant="h4" component="h1" gutterBottom>
        GULP Scraper Controls
      </Typography>
      
      <Box sx={{ mb: 4 }}>
        <Typography variant="body1" paragraph>
          This page allows you to control the GULP job scraper and view its current status.
          You can manually trigger a new scrape or view information about the last scrape.
        </Typography>
      </Box>
      
      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}
      
      {success && (
        <Alert severity="success" sx={{ mb: 3 }}>
          {success}
        </Alert>
      )}
      
      <Grid container spacing={3}>
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3, mb: 3 }}>
            <Typography variant="h6" gutterBottom>
              Scraper Status
            </Typography>
            
            {loading && !status ? (
              <Box sx={{ display: 'flex', justifyContent: 'center', my: 3 }}>
                <CircularProgress />
              </Box>
            ) : status ? (
              <List dense>
                <ListItem>
                  <ListItemText 
                    primary="Status" 
                    secondary={status.is_scraping ? 'Running' : 'Idle'} 
                    secondaryTypographyProps={{
                      color: status.is_scraping ? 'primary' : 'textSecondary'
                    }}
                  />
                </ListItem>
                <ListItem>
                  <ListItemText 
                    primary="Last Scrape" 
                    secondary={formatDate(status.last_scrape)} 
                  />
                </ListItem>
                <ListItem>
                  <ListItemText 
                    primary="Data Available" 
                    secondary={status.data_available ? 'Yes' : 'No'} 
                  />
                </ListItem>
                <ListItem>
                  <ListItemText 
                    primary="Project Count" 
                    secondary={status.project_count} 
                  />
                </ListItem>
              </List>
            ) : (
              <Typography color="text.secondary">
                Status information not available
              </Typography>
            )}
            
            <Box sx={{ mt: 2, display: 'flex', justifyContent: 'flex-end' }}>
              <Button 
                startIcon={<RefreshIcon />} 
                onClick={handleRefresh}
                disabled={loading}
              >
                Refresh Status
              </Button>
            </Box>
          </Paper>
        </Grid>
        
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3, mb: 3 }}>
            <Typography variant="h6" gutterBottom>
              Trigger Scrape
            </Typography>
            
            <Box sx={{ mb: 3 }}>
              <TextField
                label="Pages to Scrape"
                helperText="Enter page range (e.g., 1-5) or comma-separated pages (e.g., 1,3,5)"
                fullWidth
                value={pages}
                onChange={(e) => setPages(e.target.value)}
                margin="normal"
                disabled={loading || status?.is_scraping}
              />
            </Box>
            
            <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
              <Button
                variant="contained"
                color="primary"
                startIcon={<PlayArrowIcon />}
                onClick={handleStartScrape}
                disabled={loading || status?.is_scraping}
              >
                {status?.is_scraping ? 'Scrape in Progress...' : 'Start Scrape'}
              </Button>
            </Box>
          </Paper>
          
          <Card>
            <CardContent>
              <Typography variant="subtitle2" color="text.secondary">
                Note: The scraper runs automatically once per day at 3:00 AM. 
                Manual scraping should only be used when necessary.
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Container>
  );
};

export default ScraperPage;
