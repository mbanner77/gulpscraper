import React, { useState, useEffect } from 'react';
import {
  Box,
  Button,
  Card,
  CardContent,
  Typography,
  TextField,
  CircularProgress,
  Alert,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Chip,
  Stack,
  Divider
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import { getAIConfig } from '../utils/aiConfig';

/**
 * Component for AI-powered project analysis
 * Uses Hugging Face Inference API for free AI capabilities
 */
const AIProjectAnalyzer = ({ project, onClose }) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const [customPrompt, setCustomPrompt] = useState('');
  const [analysisType, setAnalysisType] = useState('skills');
  const [config, setConfig] = useState(null);
  
  // Lade KI-Konfiguration beim Komponenten-Mount
  useEffect(() => {
    const aiConfig = getAIConfig();
    setConfig(aiConfig);
  }, []);

  // Available free models
  const availableModels = [
    { id: 'google/flan-t5-small', name: 'Flan-T5 Small (schnell)', type: 'text' },
    { id: 'google/flan-t5-base', name: 'Flan-T5 Base (ausgewogen)', type: 'text' },
    { id: 'gpt2', name: 'GPT-2 (kreativ)', type: 'text' }
  ];

  // Analysis types
  const analysisTypes = [
    { id: 'skills', name: 'Benötigte Skills', prompt: 'Welche Fähigkeiten und Technologien werden für dieses Projekt benötigt? Liste sie als Stichpunkte auf.' },
    { id: 'summary', name: 'Projektzusammenfassung', prompt: 'Fasse dieses Projekt in 3-5 Sätzen zusammen.' },
    { id: 'salary', name: 'Gehaltseinschätzung', prompt: 'Schätze den möglichen Tagessatz für dieses Projekt basierend auf den Anforderungen und dem Standort. Gib eine Spanne an.' },
    { id: 'custom', name: 'Benutzerdefinierte Analyse', prompt: '' }
  ];

  // Get the current analysis type object
  const currentAnalysisType = analysisTypes.find(type => type.id === analysisType);

  // Prepare project data for analysis
  const prepareProjectData = () => {
    const { title, description, location, skills, companyName } = project;
    
    return `
Projekttitel: ${title || 'Nicht angegeben'}
Beschreibung: ${description || 'Keine Beschreibung verfügbar'}
Standort: ${location || 'Nicht angegeben'}
Firma: ${companyName || 'Nicht angegeben'}
Skills: ${Array.isArray(skills) ? skills.join(', ') : (skills || 'Keine Skills angegeben')}
    `.trim();
  };

  // Generate the prompt for the AI model
  const generatePrompt = () => {
    if (analysisType === 'custom') {
      return `${prepareProjectData()}\n\n${customPrompt}`;
    }
    return `${prepareProjectData()}\n\n${currentAnalysisType.prompt}`;
  };

  // Call the Hugging Face Inference API
  const analyzeProject = async () => {
    if (!config) {
      setError('KI-Konfiguration konnte nicht geladen werden.');
      return;
    }
    
    setLoading(true);
    setError(null);
    
    try {
      const prompt = generatePrompt();
      const selectedModel = config.defaultModel;
      
      // Use the Hugging Face Inference API (requires API key in production)
      // For demo purposes, we'll simulate a response
      
      // In a real implementation, you would make an API call like this:
      /*
      const apiKey = config.apiKey || process.env.REACT_APP_HUGGINGFACE_API_KEY;
      
      if (!apiKey) {
        console.warn('Kein API-Schlüssel gefunden, verwende eingeschränkten Zugriff');
      }
      
      const response = await fetch(
        `https://api-inference.huggingface.co/models/${selectedModel}`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(apiKey && { 'Authorization': `Bearer ${apiKey}` })
          },
          body: JSON.stringify({ 
            inputs: prompt,
            parameters: {
              max_new_tokens: config.maxTokens || 100
            }
          }),
        }
      );
      
      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }
      
      const data = await response.json();
      setResult(data[0].generated_text);
      */
      
      // Simulate API response for demo
      await new Promise(resolve => setTimeout(resolve, 1500));
      
      let simulatedResponse;
      
      switch (analysisType) {
        case 'skills':
          simulatedResponse = `
- JavaScript/TypeScript
- React.js
- Node.js
- RESTful APIs
- Git/GitHub
- Agile Entwicklungsmethoden
- Erfahrung mit Cloud-Diensten (AWS/Azure)
- CI/CD Pipelines
          `.trim();
          break;
          
        case 'summary':
          simulatedResponse = `
Das Projekt umfasst die Entwicklung einer modernen Webanwendung mit React.js und Node.js. Es handelt sich um eine Full-Stack-Entwicklung mit Fokus auf Benutzerfreundlichkeit und Skalierbarkeit. Der Entwickler wird in einem agilen Team arbeiten und sollte Erfahrung mit Cloud-Diensten und CI/CD-Prozessen mitbringen.
          `.trim();
          break;
          
        case 'salary':
          simulatedResponse = `
Basierend auf den Anforderungen und dem Standort würde ich einen Tagessatz zwischen 750€ und 950€ schätzen. Die Spanne kann je nach genauer Erfahrung und Spezialisierung variieren.
          `.trim();
          break;
          
        case 'custom':
          simulatedResponse = `
Hier ist eine benutzerdefinierte Analyse basierend auf Ihrer Anfrage. In einer Produktivumgebung würde diese Antwort vom ausgewählten KI-Modell generiert werden.
          `.trim();
          break;
          
        default:
          simulatedResponse = 'Analyse abgeschlossen.';
      }
      
      setResult(simulatedResponse);
    } catch (err) {
      console.error('Error analyzing project:', err);
      setError('Fehler bei der Analyse. Bitte versuchen Sie es später erneut.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card sx={{ mb: 3 }}>
      <CardContent>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
          <SmartToyIcon sx={{ mr: 1 }} />
          <Typography variant="h6">KI-Projektanalyse</Typography>
        </Box>
        
        <Divider sx={{ mb: 2 }} />
        
        <Box sx={{ mb: 3 }}>
          <FormControl fullWidth size="small" sx={{ mb: 2 }}>
            <InputLabel>Analysetyp</InputLabel>
            <Select
              value={analysisType}
              onChange={(e) => setAnalysisType(e.target.value)}
              label="Analysetyp"
            >
              {analysisTypes.map((type) => (
                <MenuItem key={type.id} value={type.id}>{type.name}</MenuItem>
              ))}
            </Select>
          </FormControl>
          
          {analysisType === 'custom' && (
            <TextField
              fullWidth
              multiline
              rows={3}
              label="Benutzerdefinierte Anfrage"
              variant="outlined"
              size="small"
              value={customPrompt}
              onChange={(e) => setCustomPrompt(e.target.value)}
              placeholder="Stellen Sie Ihre Frage zum Projekt..."
              sx={{ mb: 2 }}
            />
          )}
          
          <Box sx={{ mb: 2 }}>
            <Typography variant="body2" color="text.secondary">
              Verwendetes Modell: {config ? availableModels.find(m => m.id === config.defaultModel)?.name || config.defaultModel : 'Wird geladen...'}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              Konfigurieren Sie die KI-Einstellungen auf der KI-Seite
            </Typography>
          </Box>
          
          <Button
            variant="contained"
            onClick={analyzeProject}
            disabled={loading || (analysisType === 'custom' && !customPrompt.trim())}
            fullWidth
          >
            {loading ? <CircularProgress size={24} /> : 'Projekt analysieren'}
          </Button>
        </Box>
        
        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}
        
        {result && (
          <Paper variant="outlined" sx={{ p: 2, bgcolor: 'background.paper' }}>
            <Typography variant="subtitle1" gutterBottom>
              Analyseergebnis:
            </Typography>
            <Typography variant="body2" component="div" sx={{ whiteSpace: 'pre-line' }}>
              {result}
            </Typography>
          </Paper>
        )}
      </CardContent>
    </Card>
  );
};

export default AIProjectAnalyzer;
