import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { Box } from '@mui/material';
import Header from './components/Header';
import Footer from './components/Footer';
import HomePage from './pages/HomePage';
import ProjectDetailsPage from './pages/ProjectDetailsPage';
import FavoritesPage from './pages/FavoritesPage';
import ScraperPage from './pages/ScraperPage';
import ScraperControlPage from './pages/ScraperControlPage';
import AIPage from './pages/AIPage';
import DocumentsPage from './pages/DocumentsPage';
import NotFoundPage from './pages/NotFoundPage';

function App() {
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
      <Header />
      <Box component="main" sx={{ flexGrow: 1, p: { xs: 2, md: 3 } }}>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/project/:id" element={<ProjectDetailsPage />} />
          <Route path="/favorites" element={<FavoritesPage />} />
          <Route path="/scraper" element={<ScraperControlPage />} />
          <Route path="/ai" element={<AIPage />} />
          <Route path="/documents" element={<DocumentsPage />} />
          <Route path="/scraper-control" element={<Navigate to="/scraper" replace />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </Box>
      <Footer />
    </Box>
  );
}

export default App;
