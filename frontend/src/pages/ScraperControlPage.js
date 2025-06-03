import React, { useState, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Container, Paper, Tabs, Tab, Box, Typography, Divider } from '@mui/material';
import ScraperControl from '../components/ScraperControl';
import EmailConfigForm from '../components/EmailConfigForm';
import SchedulerConfigForm from '../components/SchedulerConfigForm';
import ProjectArchive from '../components/ProjectArchive';

const ScraperControlPage = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const queryParams = new URLSearchParams(location.search);
  const tabParam = queryParams.get('tab');
  
  const [tabValue, setTabValue] = useState(tabParam ? parseInt(tabParam) : 0);

  useEffect(() => {
    // Update URL when tab changes
    const params = new URLSearchParams();
    if (tabValue > 0) {
      params.set('tab', tabValue.toString());
    }
    navigate({ search: params.toString() }, { replace: true });
  }, [tabValue, navigate]);

  const handleTabChange = (event, newValue) => {
    setTabValue(newValue);
  };

  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 8 }}>
      <Typography variant="h4" component="h1" gutterBottom>
        Scraper-Verwaltung
      </Typography>
      
      <Typography variant="body1" color="text.secondary" paragraph>
        Hier können Sie den GULP-Scraper manuell starten, den Zeitplan konfigurieren und E-Mail-Benachrichtigungen einrichten.
      </Typography>
      
      <Divider sx={{ my: 3 }} />
      
      <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 3 }}>
        <Tabs 
          value={tabValue} 
          onChange={handleTabChange}
          aria-label="scraper management tabs"
        >
          <Tab label="Scraper-Steuerung" id="tab-0" />
          <Tab label="Zeitplan-Konfiguration" id="tab-1" />
          <Tab label="E-Mail-Konfiguration" id="tab-2" />
          <Tab label="Projekt-Archiv" id="tab-3" />
        </Tabs>
      </Box>
      
      <Box role="tabpanel" hidden={tabValue !== 0}>
        {tabValue === 0 && <ScraperControl />}
      </Box>
      
      <Box role="tabpanel" hidden={tabValue !== 1}>
        {tabValue === 1 && <SchedulerConfigForm />}
      </Box>
      
      <Box role="tabpanel" hidden={tabValue !== 2}>
        {tabValue === 2 && <EmailConfigForm />}
      </Box>
      
      <Box role="tabpanel" hidden={tabValue !== 3}>
        {tabValue === 3 && <ProjectArchive />}
      </Box>
    </Container>
  );
};

export default ScraperControlPage;
