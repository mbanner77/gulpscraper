import React from 'react';
import { Link as RouterLink } from 'react-router-dom';
import { Container, Typography, Button, Box, Paper } from '@mui/material';
import { Home as HomeIcon } from '@mui/icons-material';

function NotFoundPage() {
  return (
    <Container maxWidth="md">
      <Paper sx={{ p: 4, my: 4, textAlign: 'center' }}>
        <Typography variant="h2" component="h1" gutterBottom>
          404
        </Typography>
        <Typography variant="h5" component="h2" gutterBottom>
          Seite nicht gefunden
        </Typography>
        <Typography variant="body1" paragraph>
          Die von Ihnen gesuchte Seite existiert nicht oder wurde verschoben.
        </Typography>
        <Box sx={{ mt: 4 }}>
          <Button
            variant="contained"
            color="primary"
            startIcon={<HomeIcon />}
            component={RouterLink}
            to="/"
          >
            Zurück zur Startseite
          </Button>
        </Box>
      </Paper>
    </Container>
  );
}

export default NotFoundPage;
