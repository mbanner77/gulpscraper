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
  TextField,
  InputAdornment,
  Slider,
  Stack
} from '@mui/material';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import CalendarMonthIcon from '@mui/icons-material/CalendarMonth';
import { getSchedulerConfig, setSchedulerConfig } from '../services/api';

const SchedulerConfigForm = () => {
  const [config, setConfig] = useState({
    hour: 3,
    minute: 0,
    enabled: true,
    interval_days: 1
  });
  
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  
  useEffect(() => {
    fetchConfig();
  }, []);
  
  const fetchConfig = async () => {
    try {
      setLoading(true);
      const data = await getSchedulerConfig();
      setConfig(data);
      setError(null);
    } catch (err) {
      console.error('Fehler beim Laden der Scheduler-Konfiguration:', err);
      setError('Die Scheduler-Konfiguration konnte nicht geladen werden.');
    } finally {
      setLoading(false);
    }
  };
  
  const handleSubmit = async (e) => {
    e.preventDefault();
    
    try {
      setSaving(true);
      setError(null);
      setSuccess(null);
      
      await setSchedulerConfig(config);
      
      setSuccess('Scheduler-Konfiguration wurde erfolgreich gespeichert!');
      
      // Erfolgsmeldung nach 5 Sekunden ausblenden
      setTimeout(() => setSuccess(null), 5000);
    } catch (err) {
      console.error('Fehler beim Speichern der Scheduler-Konfiguration:', err);
      
      if (err.response && err.response.data && err.response.data.error) {
        setError(err.response.data.error);
      } else {
        setError('Die Scheduler-Konfiguration konnte nicht gespeichert werden.');
      }
    } finally {
      setSaving(false);
    }
  };
  
  const handleChange = (field) => (event) => {
    const value = field === 'enabled' ? event.target.checked : 
                  (field === 'interval_days' || field === 'hour' || field === 'minute') ? 
                  parseInt(event.target.value, 10) : 
                  event.target.value;
    
    setConfig({
      ...config,
      [field]: value
    });
  };
  
  const formatTime = (hour, minute) => {
    return `${hour.toString().padStart(2, '0')}:${minute.toString().padStart(2, '0')}`;
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
        Scheduler-Konfiguration
      </Typography>
      
      <Typography variant="body2" color="text.secondary" paragraph>
        Konfigurieren Sie, wann und wie oft der Scraper automatisch ausgeführt werden soll.
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
      
      <form onSubmit={handleSubmit}>
        <Grid container spacing={3}>
          <Grid item xs={12}>
            <FormControlLabel
              control={
                <Switch
                  checked={config.enabled}
                  onChange={handleChange('enabled')}
                  color="primary"
                />
              }
              label="Automatische Ausführung aktivieren"
            />
          </Grid>
          
          <Grid item xs={12} sm={6}>
            <Typography variant="subtitle2" gutterBottom>
              Uhrzeit der Ausführung
            </Typography>
            <Stack direction="row" spacing={2} alignItems="center">
              <TextField
                label="Stunde"
                type="number"
                value={config.hour}
                onChange={handleChange('hour')}
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <AccessTimeIcon fontSize="small" />
                    </InputAdornment>
                  ),
                }}
                inputProps={{
                  min: 0,
                  max: 23,
                  step: 1
                }}
                disabled={!config.enabled}
                sx={{ width: '45%' }}
              />
              <Typography variant="body1">:</Typography>
              <TextField
                label="Minute"
                type="number"
                value={config.minute}
                onChange={handleChange('minute')}
                inputProps={{
                  min: 0,
                  max: 59,
                  step: 1
                }}
                disabled={!config.enabled}
                sx={{ width: '45%' }}
              />
            </Stack>
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
              Der Scraper wird täglich um {formatTime(config.hour, config.minute)} Uhr ausgeführt.
            </Typography>
          </Grid>
          
          <Grid item xs={12} sm={6}>
            <Typography variant="subtitle2" gutterBottom>
              Ausführungsintervall (Tage)
            </Typography>
            <Box sx={{ display: 'flex', alignItems: 'center' }}>
              <CalendarMonthIcon sx={{ mr: 1, color: 'text.secondary' }} />
              <TextField
                type="number"
                fullWidth
                value={config.interval_days}
                onChange={handleChange('interval_days')}
                inputProps={{
                  min: 1,
                  max: 30,
                  step: 1
                }}
                disabled={!config.enabled}
              />
            </Box>
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
              {config.interval_days === 1 
                ? 'Der Scraper wird täglich ausgeführt.' 
                : `Der Scraper wird alle ${config.interval_days} Tage ausgeführt.`}
            </Typography>
          </Grid>
          
          <Grid item xs={12}>
            <Button
              type="submit"
              variant="contained"
              color="primary"
              disabled={saving}
              startIcon={saving ? <CircularProgress size={20} color="inherit" /> : null}
            >
              {saving ? 'Wird gespeichert...' : 'Konfiguration speichern'}
            </Button>
          </Grid>
        </Grid>
      </form>
    </Paper>
  );
};

export default SchedulerConfigForm;
