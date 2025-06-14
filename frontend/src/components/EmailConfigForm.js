import React, { useState, useEffect } from 'react';
import {
  Box,
  Paper,
  Typography,
  TextField,
  Button,
  Switch,
  FormControlLabel,
  CircularProgress,
  Alert,
  Divider,
  Grid,
  InputAdornment,
  IconButton,
  Tooltip
} from '@mui/material';
import VisibilityIcon from '@mui/icons-material/Visibility';
import VisibilityOffIcon from '@mui/icons-material/VisibilityOff';
import SaveIcon from '@mui/icons-material/Save';
import SendIcon from '@mui/icons-material/Send';
import InfoIcon from '@mui/icons-material/Info';
import { getEmailConfig, setEmailConfig, testEmailConfig } from '../services/api';

const EmailConfigForm = () => {
  const [config, setConfig] = useState({
    smtp_host: '',
    smtp_port: 587,
    smtp_user: '',
    smtp_password: '',
    sender: '',
    recipient: '',
    enabled: true,
    frontend_url: window.location.origin
  });
  
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [showPassword, setShowPassword] = useState(false);
  const [testResult, setTestResult] = useState(null);
  
  useEffect(() => {
    fetchConfig();
  }, []);
  
  const fetchConfig = async () => {
    try {
      setLoading(true);
      const data = await getEmailConfig();
      
      // Nur Felder aktualisieren, die tatsächlich zurückgegeben wurden
      const newConfig = { ...config };
      for (const key in data) {
        if (key in newConfig && data[key] !== null) {
          newConfig[key] = data[key];
        }
      }
      
      setConfig(newConfig);
      setError(null);
    } catch (err) {
      console.error('Fehler beim Laden der E-Mail-Konfiguration:', err);
      setError('Die E-Mail-Konfiguration konnte nicht geladen werden.');
    } finally {
      setLoading(false);
    }
  };
  
  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setConfig({
      ...config,
      [name]: type === 'checkbox' ? checked : value
    });
  };
  
  const handleSubmit = async (e) => {
    e.preventDefault();
    
    try {
      setSaving(true);
      setError(null);
      
      // Validierung
      if (!config.smtp_host) {
        setError('Bitte geben Sie einen SMTP-Server an.');
        setSaving(false);
        return;
      }
      
      if (!config.smtp_user) {
        setError('Bitte geben Sie einen SMTP-Benutzernamen an.');
        setSaving(false);
        return;
      }
      
      if (!config.smtp_password) {
        setError('Bitte geben Sie ein SMTP-Passwort an.');
        setSaving(false);
        return;
      }
      
      if (!config.recipient) {
        setError('Bitte geben Sie eine Empfänger-E-Mail-Adresse an.');
        setSaving(false);
        return;
      }
      
      // Konfiguration speichern
      const result = await setEmailConfig(config);
      
      setSuccess('E-Mail-Konfiguration erfolgreich gespeichert!');
      
      // Erfolgsmeldung nach 5 Sekunden ausblenden
      setTimeout(() => setSuccess(null), 5000);
    } catch (err) {
      console.error('Fehler beim Speichern der E-Mail-Konfiguration:', err);
      setError('Die E-Mail-Konfiguration konnte nicht gespeichert werden.');
    } finally {
      setSaving(false);
    }
  };
  
  const togglePasswordVisibility = () => {
    setShowPassword(!showPassword);
  };
  
  const handleTestEmail = async () => {
    try {
      setTesting(true);
      setTestResult(null);
      setError(null);
      
      if (!config.recipient) {
        setError('Bitte geben Sie eine Empfänger-E-Mail-Adresse an.');
        setTesting(false);
        return;
      }
      
      const result = await testEmailConfig(config.recipient);
      
      if (result.success) {
        setTestResult({
          success: true,
          message: result.message
        });
      } else {
        setTestResult({
          success: false,
          message: result.message || 'Fehler beim Senden der Test-E-Mail.'
        });
      }
      
      // Testresultat nach 10 Sekunden ausblenden
      setTimeout(() => setTestResult(null), 10000);
    } catch (err) {
      console.error('Fehler beim Testen der E-Mail-Konfiguration:', err);
      setTestResult({
        success: false,
        message: 'Fehler beim Testen der E-Mail-Konfiguration.'
      });
    } finally {
      setTesting(false);
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
        E-Mail-Benachrichtigungen
      </Typography>
      
      <Typography variant="body2" color="text.secondary" paragraph>
        Konfigurieren Sie E-Mail-Benachrichtigungen für neue Projekte. Sie erhalten eine E-Mail, wenn neue Projekte gefunden werden.
      </Typography>
      
      <Alert severity="info" sx={{ mb: 2 }} icon={<InfoIcon />}>
        Die Standard-SMTP-Konfiguration ist bereits eingerichtet (mail.tk-core.de). Sie können die Test-E-Mail-Funktion nutzen, um die Konfiguration zu überprüfen.
      </Alert>
      
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
      
      {testResult && (
        <Alert severity={testResult.success ? "success" : "error"} sx={{ mb: 2 }}>
          {testResult.message}
        </Alert>
      )}
      
      <form onSubmit={handleSubmit}>
        <Grid container spacing={2}>
          <Grid item xs={12}>
            <FormControlLabel
              control={
                <Switch
                  checked={config.enabled}
                  onChange={handleChange}
                  name="enabled"
                  color="primary"
                />
              }
              label="E-Mail-Benachrichtigungen aktivieren"
            />
          </Grid>
          
          <Grid item xs={12} sm={8}>
            <TextField
              fullWidth
              label="SMTP-Server"
              name="smtp_host"
              value={config.smtp_host}
              onChange={handleChange}
              disabled={saving}
              required
              helperText="z.B. smtp.gmail.com"
            />
          </Grid>
          
          <Grid item xs={12} sm={4}>
            <TextField
              fullWidth
              label="SMTP-Port"
              name="smtp_port"
              type="number"
              value={config.smtp_port}
              onChange={handleChange}
              disabled={saving}
              required
              helperText="Standard: 587"
            />
          </Grid>
          
          <Grid item xs={12}>
            <TextField
              fullWidth
              label="SMTP-Benutzername"
              name="smtp_user"
              value={config.smtp_user}
              onChange={handleChange}
              disabled={saving}
              required
              helperText="Meist Ihre E-Mail-Adresse"
            />
          </Grid>
          
          <Grid item xs={12}>
            <TextField
              fullWidth
              label="SMTP-Passwort"
              name="smtp_password"
              type={showPassword ? 'text' : 'password'}
              value={config.smtp_password}
              onChange={handleChange}
              disabled={saving}
              required
              helperText="Für Google: App-Passwort verwenden"
              InputProps={{
                endAdornment: (
                  <InputAdornment position="end">
                    <IconButton
                      onClick={togglePasswordVisibility}
                      edge="end"
                    >
                      {showPassword ? <VisibilityOffIcon /> : <VisibilityIcon />}
                    </IconButton>
                  </InputAdornment>
                )
              }}
            />
          </Grid>
          
          <Grid item xs={12}>
            <TextField
              fullWidth
              label="Absender (optional)"
              name="sender"
              value={config.sender}
              onChange={handleChange}
              disabled={saving}
              helperText="z.B. 'GULP Scraper <noreply@example.com>'"
            />
          </Grid>
          
          <Grid item xs={12}>
            <TextField
              fullWidth
              label="Empfänger-E-Mail"
              name="recipient"
              type="email"
              value={config.recipient}
              onChange={handleChange}
              disabled={saving}
              required
              helperText="An diese Adresse werden Benachrichtigungen gesendet"
            />
          </Grid>
          
          <Grid item xs={12}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mt: 2 }}>
              <Tooltip title="Sendet eine Test-E-Mail an die angegebene Empfänger-Adresse">
                <Button
                  variant="outlined"
                  color="secondary"
                  disabled={testing || saving}
                  onClick={handleTestEmail}
                  startIcon={testing ? <CircularProgress size={20} /> : <SendIcon />}
                >
                  {testing ? 'Wird gesendet...' : 'Test-E-Mail senden'}
                </Button>
              </Tooltip>
              
              <Button
                type="submit"
                variant="contained"
                color="primary"
                disabled={saving || testing}
                startIcon={saving ? <CircularProgress size={20} /> : <SaveIcon />}
              >
                {saving ? 'Wird gespeichert...' : 'Konfiguration speichern'}
              </Button>
            </Box>
          </Grid>
        </Grid>
      </form>
    </Paper>
  );
};

export default EmailConfigForm;
