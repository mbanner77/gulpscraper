import React, { useState, useEffect } from 'react';
import {
  Box,
  Paper,
  Typography,
  Button,
  CircularProgress,
  Alert,
  Divider,
  FormControlLabel,
  Switch,
  Grid,
  Card,
  CardContent,
  Chip
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import MailOutlineIcon from '@mui/icons-material/MailOutline';
import { triggerScrape, getScraperStatus } from '../services/api';

const ScraperControl = () => {
  const [status, setStatus] = useState({
    is_scraping: false,
    last_scrape: null,
    data_available: false,
    project_count: 0,
    new_project_count: 0,
    total_projects_found: 0,
    email_notification: {
      enabled: false,
      recipient: null,
      configured: false
    }
  });
  
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [sendEmail, setSendEmail] = useState(false);
  const [statusPolling, setStatusPolling] = useState(null);
  
  useEffect(() => {
    fetchStatus();
    
    // Polling starten, wenn die Komponente geladen wird
    const interval = setInterval(fetchStatus, 5000);
    setStatusPolling(interval);
    
    // Cleanup beim Unmount
    return () => {
      if (statusPolling) {
        clearInterval(statusPolling);
      }
    };
  }, []);
  
  const fetchStatus = async () => {
    try {
      const data = await getScraperStatus();
      setStatus(data);
      
      // E-Mail-Benachrichtigung standardmäßig aktivieren, wenn konfiguriert
      if (data.email_notification.configured && !loading) {
        setSendEmail(data.email_notification.enabled);
      }
      
      setError(null);
    } catch (err) {
      console.error('Fehler beim Laden des Scraper-Status:', err);
      setError('Der Scraper-Status konnte nicht geladen werden.');
    } finally {
      setLoading(false);
    }
  };
  
  const handleStartScrape = async () => {
    try {
      setError(null);
      setSuccess(null);
      
      const result = await triggerScrape({ send_email: sendEmail });
      
      setSuccess('Scraper wurde erfolgreich gestartet!');
      
      // Status sofort aktualisieren
      fetchStatus();
      
      // Erfolgsmeldung nach 5 Sekunden ausblenden
      setTimeout(() => setSuccess(null), 5000);
    } catch (err) {
      console.error('Fehler beim Starten des Scrapers:', err);
      
      if (err.response && err.response.status === 409) {
        setError('Ein Scrape-Vorgang läuft bereits.');
      } else {
        setError('Der Scraper konnte nicht gestartet werden.');
      }
    }
  };
  
  const formatDate = (dateString) => {
    if (!dateString) return 'Nie';
    
    try {
      const date = new Date(dateString);
      return new Intl.DateTimeFormat('de-DE', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
      }).format(date);
    } catch (e) {
      return dateString;
    }
  };
  
  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', my: 4 }}>
        <CircularProgress />
      </Box>
    );
  }
  
  return (
    <Paper sx={{ p: 3, mb: 4 }}>
      <Typography variant="h6" gutterBottom>
        Scraper-Steuerung
      </Typography>
      
      <Typography variant="body2" color="text.secondary" paragraph>
        Starten Sie den Scraper manuell und sehen Sie den aktuellen Status.
      </Typography>
      
      <Divider sx={{ my: 2 }} />
      
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}
      
      {success && (
        <Alert severity="success" sx={{ mb: 2 }}>
          {success}
        </Alert>
      )}
      
      <Grid container spacing={3}>
        <Grid item xs={12} md={6}>
          <Card variant="outlined">
            <CardContent>
              <Typography variant="subtitle1" gutterBottom>
                Status
              </Typography>
              
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                  <Typography variant="body2" color="text.secondary">
                    Scraper aktiv:
                  </Typography>
                  <Chip 
                    size="small"
                    color={status.is_scraping ? "primary" : "default"}
                    label={status.is_scraping ? "Aktiv" : "Inaktiv"}
                  />
                </Box>
                
                <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                  <Typography variant="body2" color="text.secondary">
                    Letzter Lauf:
                  </Typography>
                  <Typography variant="body2">
                    {status.last_scrape ? new Date(status.last_scrape).toLocaleString('de-DE') : 'Noch nie'}
                  </Typography>
                </Box>

                <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                  <Typography variant="body2" color="text.secondary">
                    Zeitplan:
                  </Typography>
                  <Typography variant="body2">
                    {status.scheduler && status.scheduler.enabled && status.scheduler.formatted_runs
                      ? `${status.scheduler.formatted_runs.join(', ')} Uhr${status.scheduler.interval_days > 1 ? `, alle ${status.scheduler.interval_days} Tage` : ' täglich'}` 
                      : 'Deaktiviert'}
                  </Typography>
                </Box>
                
                <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                  <Typography variant="body2" color="text.secondary">
                    Nächster geplanter Lauf:
                  </Typography>
                  <Typography variant="body2">
                    {status.next_scheduled_run ? new Date(status.next_scheduled_run).toLocaleString('de-DE') : 'Nicht geplant'}
                  </Typography>
                </Box>
                
                <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                  <Typography variant="body2" color="text.secondary">
                    Projekte gesamt:
                  </Typography>
                  <Typography variant="body2">
                    {status.project_count}
                  </Typography>
                </Box>
                
                <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                  <Typography variant="body2" color="text.secondary">
                    Neue Projekte:
                  </Typography>
                  <Typography variant="body2" color={status.new_project_count > 0 ? "success.main" : "text.primary"} fontWeight={status.new_project_count > 0 ? "bold" : "normal"}>
                    {status.new_project_count}
                  </Typography>
                </Box>
                
                <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                  <Typography variant="body2" color="text.secondary">
                    Projekte insgesamt gefunden:
                  </Typography>
                  <Typography variant="body2">
                    {status.total_projects_found}
                  </Typography>
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Grid>
        
        <Grid item xs={12} md={6}>
          <Card variant="outlined">
            <CardContent>
              <Typography variant="subtitle1" gutterBottom>
                Aktionen
              </Typography>
              
              <Box sx={{ mb: 2 }}>
                <FormControlLabel
                  control={
                    <Switch
                      checked={sendEmail}
                      onChange={(e) => setSendEmail(e.target.checked)}
                      disabled={!status.email_notification.configured}
                      color="primary"
                    />
                  }
                  label={
                    <Box sx={{ display: 'flex', alignItems: 'center' }}>
                      <Typography variant="body2">
                        E-Mail-Benachrichtigung senden
                      </Typography>
                      {!status.email_notification.configured && (
                        <Typography variant="caption" color="error" sx={{ ml: 1 }}>
                          (Nicht konfiguriert)
                        </Typography>
                      )}
                    </Box>
                  }
                />
                
                {status.email_notification.configured && status.email_notification.recipient && (
                  <Typography variant="caption" color="text.secondary" sx={{ display: 'block', ml: 4 }}>
                    An: {status.email_notification.recipient}
                  </Typography>
                )}
              </Box>
              
              <Button
                variant="contained"
                color="primary"
                startIcon={status.is_scraping ? <CircularProgress size={20} color="inherit" /> : <RefreshIcon />}
                endIcon={sendEmail && status.email_notification.configured ? <MailOutlineIcon /> : null}
                onClick={handleStartScrape}
                disabled={status.is_scraping}
                fullWidth
              >
                {status.is_scraping ? 'Scraper läuft...' : 'Scraper starten'}
              </Button>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Paper>
  );
};

export default ScraperControl;
