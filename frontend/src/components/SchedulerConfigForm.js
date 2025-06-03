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
  IconButton,
  Card,
  CardContent,
  Stack
} from '@mui/material';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import CalendarMonthIcon from '@mui/icons-material/CalendarMonth';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import { getSchedulerConfig, setSchedulerConfig } from '../services/api';

const SchedulerConfigForm = () => {
  // Initialize with default values to prevent undefined errors
  const [config, setConfig] = useState({
    enabled: true,
    interval_days: 1,
    daily_runs: [
      { hour: 3, minute: 0 }
    ]
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
      
      // Make sure we have a valid data object
      if (!data) {
        throw new Error('No configuration data received');
      }
      
      // Handle both old and new schema formats
      let configData = { ...data };
      
      // Ensure enabled property exists
      if (configData.enabled === undefined) {
        configData.enabled = true;
      }
      
      // Ensure interval_days property exists and is valid
      if (!configData.interval_days || configData.interval_days < 1) {
        configData.interval_days = 1;
      }
      
      // Handle daily_runs based on schema
      if (Array.isArray(configData.daily_runs) && configData.daily_runs.length > 0) {
        // New schema with daily_runs array - already correct
      } else if (configData.hour !== undefined && configData.minute !== undefined) {
        // Old schema with hour and minute properties
        configData.daily_runs = [{ hour: configData.hour, minute: configData.minute }];
      } else {
        // No valid run time data, use default
        configData.daily_runs = [{ hour: 3, minute: 0 }];
      }
      
      // Set the sanitized config
      setConfig(configData);
      setError(null);
    } catch (err) {
      console.error('Fehler beim Laden der Scheduler-Konfiguration:', err);
      setError('Die Scheduler-Konfiguration konnte nicht geladen werden.');
      
      // Ensure we have a valid config even on error
      setConfig({
        enabled: true,
        interval_days: 1,
        daily_runs: [{ hour: 3, minute: 0 }]
      });
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
      
      // Ensure we have a valid config to send
      const configToSend = {
        enabled: config.enabled !== undefined ? config.enabled : true,
        interval_days: config.interval_days || 1,
        daily_runs: Array.isArray(config.daily_runs) && config.daily_runs.length > 0 
          ? config.daily_runs 
          : [{ hour: 3, minute: 0 }]
      };
      
      await setSchedulerConfig(configToSend);
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
                  field === 'interval_days' ? parseInt(event.target.value, 10) : 
                  event.target.value;
    
    setConfig(prev => ({
      ...prev,
      [field]: value
    }));
  };
  
  const handleRunChange = (index, field) => (event) => {
    const value = parseInt(event.target.value, 10);
    
    setConfig(prev => {
      // Ensure daily_runs exists and is an array
      const dailyRuns = Array.isArray(prev.daily_runs) ? [...prev.daily_runs] : [{ hour: 3, minute: 0 }];
      
      // Update the specific run if it exists
      if (index >= 0 && index < dailyRuns.length) {
        dailyRuns[index] = { ...dailyRuns[index], [field]: value };
      }
      
      return {
        ...prev,
        daily_runs: dailyRuns
      };
    });
  };
  
  const addRun = () => {
    setConfig(prev => {
      // Ensure daily_runs exists and is an array
      const dailyRuns = Array.isArray(prev.daily_runs) ? [...prev.daily_runs] : [];
      
      // Default to noon if there's already a morning run
      const newHour = dailyRuns.length > 0 ? 12 : 3;
      
      return {
        ...prev,
        daily_runs: [...dailyRuns, { hour: newHour, minute: 0 }]
      };
    });
  };
  
  const removeRun = (index) => {
    setConfig(prev => {
      // Ensure daily_runs exists and is an array
      const dailyRuns = Array.isArray(prev.daily_runs) ? [...prev.daily_runs] : [{ hour: 3, minute: 0 }];
      
      if (dailyRuns.length <= 1) {
        setError('Mindestens ein Ausführungszeitpunkt muss konfiguriert sein.');
        return prev;
      }
      
      return {
        ...prev,
        daily_runs: dailyRuns.filter((_, i) => i !== index)
      };
    });
  };
  
  const formatTime = (hour, minute) => {
    return `${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}`;
  };
  
  // Safe getter for daily runs count
  const getDailyRunsCount = () => {
    return Array.isArray(config.daily_runs) ? config.daily_runs.length : 0;
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
                  checked={config.enabled === undefined ? true : config.enabled}
                  onChange={handleChange('enabled')}
                  color="primary"
                />
              }
              label="Automatische Ausführung aktivieren"
            />
          </Grid>
          
          <Grid item xs={12}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
              <Typography variant="subtitle2">
                Ausführungszeiten pro Tag
              </Typography>
              <Button 
                startIcon={<AddIcon />} 
                variant="outlined" 
                size="small" 
                onClick={addRun}
                disabled={!config.enabled || getDailyRunsCount() >= 5}
              >
                Hinzufügen
              </Button>
            </Box>
            
            {Array.isArray(config.daily_runs) && config.daily_runs.map((run, index) => (
              <Card key={index} variant="outlined" sx={{ mb: 2 }}>
                <CardContent>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                    <Typography variant="subtitle2">
                      Ausführung {index + 1}
                    </Typography>
                    <IconButton 
                      size="small" 
                      color="error" 
                      onClick={() => removeRun(index)}
                      disabled={!config.enabled || getDailyRunsCount() <= 1}
                    >
                      <DeleteIcon fontSize="small" />
                    </IconButton>
                  </Box>
                  
                  <Stack direction="row" spacing={2} alignItems="center">
                    <TextField
                      label="Stunde"
                      type="number"
                      value={run.hour}
                      onChange={handleRunChange(index, 'hour')}
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
                      value={run.minute}
                      onChange={handleRunChange(index, 'minute')}
                      inputProps={{
                        min: 0,
                        max: 59,
                        step: 1
                      }}
                      disabled={!config.enabled}
                      sx={{ width: '45%' }}
                    />
                  </Stack>
                </CardContent>
              </Card>
            ))}
            
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
              {!Array.isArray(config.daily_runs) || config.daily_runs.length === 0
                ? 'Keine Ausführungszeiten konfiguriert.'
                : config.daily_runs.length === 1 && config.daily_runs[0] && config.daily_runs[0].hour !== undefined
                  ? `Der Scraper wird täglich um ${formatTime(config.daily_runs[0].hour, config.daily_runs[0].minute)} Uhr ausgeführt.`
                  : `Der Scraper wird täglich zu ${getDailyRunsCount()} verschiedenen Zeiten ausgeführt.`}
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
                value={config.interval_days || 1}
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
              {(config.interval_days || 1) === 1 
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
