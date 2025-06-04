import React from 'react';
import { Container, Typography, Box, Paper, Divider } from '@mui/material';
import AIConfigPanel from '../components/AIConfigPanel';

/**
 * AI Configuration Page
 */
const AIPage = () => {
  return (
    <Container maxWidth="lg">
      <Box sx={{ my: 4 }}>
        <Typography variant="h4" component="h1" gutterBottom>
          KI-Funktionen
        </Typography>
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
          
          <AIConfigPanel />
        </Paper>
      </Box>
    </Container>
  );
};

export default AIPage;
