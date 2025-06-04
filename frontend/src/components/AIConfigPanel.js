import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  TextField,
  Button,
  Switch,
  FormControlLabel,
  Alert,
  CircularProgress,
  Divider,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  FormHelperText
} from '@mui/material';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import SaveIcon from '@mui/icons-material/Save';

/**
 * Component for configuring AI features
 */
const AIConfigPanel = () => {
  const [loading, setLoading] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState(null);
  
  // AI configuration state
  const [config, setConfig] = useState({
    enabled: true,
    apiKey: '',
    defaultModel: 'google/flan-t5-small',
    autoAnalyze: false,
    maxTokens: 100
  });

  // Available models
  const availableModels = [
    { id: 'google/flan-t5-small', name: 'Flan-T5 Small (schnell)', type: 'text' },
    { id: 'google/flan-t5-base', name: 'Flan-T5 Base (ausgewogen)', type: 'text' },
    { id: 'gpt2', name: 'GPT-2 (kreativ)', type: 'text' }
  ];

  // Load saved configuration on component mount
  useEffect(() => {
    const loadConfig = () => {
      try {
        const savedConfig = localStorage.getItem('aiConfig');
        if (savedConfig) {
          setConfig(JSON.parse(savedConfig));
        }
      } catch (err) {
        console.error('Error loading AI configuration:', err);
      }
    };
    
    loadConfig();
  }, []);

  // Handle input changes
  const handleChange = (e) => {
    const { name, value, checked } = e.target;
    setConfig({
      ...config,
      [name]: name === 'enabled' || name === 'autoAnalyze' ? checked : value
    });
    
    // Clear saved status when changes are made
    setSaved(false);
  };

  // Save configuration
  const saveConfig = () => {
    setLoading(true);
    setError(null);
    
    try {
      localStorage.setItem('aiConfig', JSON.stringify(config));
      setSaved(true);
      
      // Reset saved status after 3 seconds
      setTimeout(() => {
        setSaved(false);
      }, 3000);
    } catch (err) {
      console.error('Error saving AI configuration:', err);
      setError('Fehler beim Speichern der Konfiguration.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card sx={{ mb: 3 }}>
      <CardContent>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
          <SmartToyIcon sx={{ mr: 1 }} />
          <Typography variant="h6">KI-Konfiguration</Typography>
        </Box>
        
        <Divider sx={{ mb: 2 }} />
        
        <Box sx={{ mb: 2 }}>
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
        
        <Box sx={{ mb: 2 }}>
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
        
        <Box sx={{ mb: 2 }}>
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
        
        <Box sx={{ mb: 2 }}>
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
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}
        
        {saved && (
          <Alert severity="success" sx={{ mb: 2 }}>
            Konfiguration erfolgreich gespeichert!
          </Alert>
        )}
        
        <Button
          variant="contained"
          startIcon={loading ? <CircularProgress size={20} /> : <SaveIcon />}
          onClick={saveConfig}
          disabled={loading}
        >
          Konfiguration speichern
        </Button>
      </CardContent>
    </Card>
  );
};

export default AIConfigPanel;
