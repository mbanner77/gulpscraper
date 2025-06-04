import React, { useState, useEffect } from 'react';
import { Container, Typography, Box, Paper, Divider, Switch, FormControlLabel, Button, TextField, FormControl, InputLabel, Select, MenuItem, FormHelperText, Alert } from '@mui/material';
import SmartToyIcon from '@mui/icons-material/SmartToy';

/**
 * AI Configuration Page
 */
const AIPage = () => {
  const [config, setConfig] = useState({
    enabled: true,
    apiKey: '',
    defaultModel: 'google/flan-t5-small',
    autoAnalyze: false,
    maxTokens: 100
  });
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState(null);

  // Verfügbare Modelle
  const availableModels = [
    { id: 'google/flan-t5-small', name: 'Flan-T5 Small (schnell)', type: 'text' },
    { id: 'google/flan-t5-base', name: 'Flan-T5 Base (ausgewogen)', type: 'text' },
    { id: 'gpt2', name: 'GPT-2 (kreativ)', type: 'text' }
  ];

  // Lade gespeicherte Konfiguration beim Komponenten-Mount
  useEffect(() => {
    try {
      const savedConfig = localStorage.getItem('aiConfig');
      if (savedConfig) {
        setConfig(JSON.parse(savedConfig));
      } else {
        // Setze Standardkonfiguration, wenn keine vorhanden ist
        localStorage.setItem('aiConfig', JSON.stringify(config));
      }
    } catch (err) {
      console.error('Fehler beim Laden der KI-Konfiguration:', err);
      setError('Fehler beim Laden der Konfiguration.');
    }
  }, []);

  // Behandle Eingabeänderungen
  const handleChange = (e) => {
    const { name, value, checked } = e.target;
    setConfig({
      ...config,
      [name]: name === 'enabled' || name === 'autoAnalyze' ? checked : value
    });
    
    // Lösche den Speicherstatus, wenn Änderungen vorgenommen werden
    setSaved(false);
  };

  // Speichere Konfiguration
  const saveConfig = () => {
    try {
      localStorage.setItem('aiConfig', JSON.stringify(config));
      setSaved(true);
      
      // Setze den Speicherstatus nach 3 Sekunden zurück
      setTimeout(() => {
        setSaved(false);
      }, 3000);
    } catch (err) {
      console.error('Fehler beim Speichern der KI-Konfiguration:', err);
      setError('Fehler beim Speichern der Konfiguration.');
    }
  };

  return (
    <Container maxWidth="lg">
      <Box sx={{ my: 4 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
          <SmartToyIcon sx={{ mr: 1, fontSize: 30 }} />
          <Typography variant="h4" component="h1">
            KI-Funktionen
          </Typography>
        </Box>
        
        <Typography variant="subtitle1" color="text.secondary" gutterBottom>
          Konfigurieren Sie die KI-Funktionen für die GULP Projekt-Analyse
        </Typography>
        
        <Paper sx={{ p: 3, mt: 3 }}>
          <Typography variant="h5" gutterBottom>
            Über die KI-Funktionen
          </Typography>
          <Typography variant="body1" paragraph>
            Diese Anwendung verwendet kostenlose oder günstige KI-Modelle von Hugging Face, um Ihnen bei der Analyse von Projekten zu helfen.
            Die KI kann Ihnen helfen, wichtige Informationen aus Projektbeschreibungen zu extrahieren, Skills zu identifizieren und Gehaltseinschätzungen vorzunehmen.
          </Typography>
          <Typography variant="body1" paragraph>
            Alle KI-Funktionen sind optional und können jederzeit aktiviert oder deaktiviert werden. Die Verarbeitung erfolgt über die Hugging Face Inference API,
            die kostenlose Nutzungskontingente bietet. Für eine bessere Leistung können Sie Ihren eigenen API-Schlüssel hinzufügen.
          </Typography>
          
          <Divider sx={{ my: 3 }} />
          
          <Box sx={{ mb: 3 }}>
            <FormControlLabel
              control={
                <Switch
                  checked={config.enabled}
                  onChange={handleChange}
                  name="enabled"
                />
              }
              label="KI-Funktionen aktivieren"
            />
            
            <FormHelperText>
              Aktiviert oder deaktiviert alle KI-Funktionen in der Anwendung
            </FormHelperText>
          </Box>
          
          <Box sx={{ mb: 3 }}>
            <TextField
              fullWidth
              label="Hugging Face API-Schlüssel (optional)"
              variant="outlined"
              size="small"
              name="apiKey"
              value={config.apiKey}
              onChange={handleChange}
              type="password"
              placeholder="hf_..."
              disabled={!config.enabled}
              sx={{ mb: 1 }}
            />
            <FormHelperText>
              Für bessere Ergebnisse können Sie einen API-Schlüssel von Hugging Face hinzufügen.
              Ohne Schlüssel werden die kostenlosen Modelle mit Ratenbegrenzung verwendet.
            </FormHelperText>
          </Box>
          
          <Box sx={{ mb: 3 }}>
            <FormControl fullWidth size="small" disabled={!config.enabled}>
              <InputLabel>Standard-KI-Modell</InputLabel>
              <Select
                name="defaultModel"
                value={config.defaultModel}
                onChange={handleChange}
                label="Standard-KI-Modell"
              >
                {availableModels.map((model) => (
                  <MenuItem key={model.id} value={model.id}>{model.name}</MenuItem>
                ))}
              </Select>
            </FormControl>
          </Box>
          
          <Box sx={{ mb: 3 }}>
            <FormControlLabel
              control={
                <Switch
                  checked={config.autoAnalyze}
                  onChange={handleChange}
                  name="autoAnalyze"
                  disabled={!config.enabled}
                />
              }
              label="Automatische Analyse"
            />
            
            <FormHelperText>
              Projekte automatisch analysieren, wenn sie geöffnet werden
            </FormHelperText>
          </Box>
          
          <Box sx={{ mb: 3 }}>
            <TextField
              fullWidth
              label="Maximale Token-Anzahl"
              variant="outlined"
              size="small"
              name="maxTokens"
              value={config.maxTokens}
              onChange={handleChange}
              type="number"
              inputProps={{ min: 50, max: 500 }}
              disabled={!config.enabled}
            />
            <FormHelperText>
              Begrenzt die Länge der KI-Antworten (50-500)
            </FormHelperText>
          </Box>
          
          {error && (
            <Alert severity="error" sx={{ mb: 3 }}>
              {error}
            </Alert>
          )}
          
          {saved && (
            <Alert severity="success" sx={{ mb: 3 }}>
              Konfiguration erfolgreich gespeichert!
            </Alert>
          )}
          
          <Button
            variant="contained"
            onClick={saveConfig}
            startIcon={<SmartToyIcon />}
          >
            Konfiguration speichern
          </Button>
        </Paper>
      </Box>
    </Container>
  );
};

export default AIPage;
