import axios from 'axios';

// Determine the API URL based on environment
const determineApiUrl = () => {
  console.log('Determining API URL for hostname:', window.location.hostname);
  
  // If explicit API URL is provided in environment, use it
  if (process.env.REACT_APP_API_URL) {
    console.log('Using explicit API URL from environment:', process.env.REACT_APP_API_URL);
    return process.env.REACT_APP_API_URL;
  }
  
  // For Render deployment: if frontend is on render.com, assume backend is too
  if (window.location.hostname.includes('render.com') || 
      window.location.hostname.includes('onrender.com')) {
    console.log('Detected Render deployment');
    
    // Verbesserte Logik für Render-Deployment
    // 1. Wenn die URL gulp-job-app.onrender.com ist, verwende gulp-job-app-api.onrender.com
    if (window.location.hostname.includes('gulp-job-app')) {
      const apiUrl = window.location.origin.replace('gulp-job-app', 'gulp-job-app-api');
      console.log('Using matched Render API URL:', apiUrl);
      return apiUrl;
    }
    
    // 2. Fallback: Extrahiere den App-Namen aus dem Hostnamen
    const hostParts = window.location.hostname.split('-');
    if (hostParts.length > 0) {
      const appPrefix = hostParts[0]; // z.B. 'gulp'
      const apiUrl = `https://${appPrefix}-backend.onrender.com`;
      console.log('Using constructed Render API URL with prefix:', apiUrl);
      return apiUrl;
    }
    
    // 3. Letzter Fallback: Ersetze 'frontend' durch 'backend'
    const fallbackUrl = window.location.origin.replace('frontend', 'backend');
    console.log('Using fallback Render API URL:', fallbackUrl);
    return fallbackUrl;
  }
  
  // Local development
  console.log('Using local development API URL');
  return 'http://localhost:8001'; // Updated to match our current port
};

const API_URL = determineApiUrl();
console.log('Using API URL:', API_URL);

// Create axios instance with base URL
const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  // Add withCredentials for CORS with credentials
  withCredentials: API_URL.includes('render.com') || API_URL.includes('onrender.com'),
});

// Get recent projects (last 24h) with optional filters
export const getProjects = async (params = {}) => {
  try {
    // Make sure we're using the correct parameter name for show_all
    const apiParams = { ...params };
    
    // If show_all is present, make sure it's sent as a string 'true' or 'false'
    if (apiParams.show_all !== undefined) {
      apiParams.show_all = apiParams.show_all.toString();
    }
    
    console.log('API call to /projects with params:', apiParams);
    const response = await api.get('/projects', { params: apiParams });
    console.log('API response status:', response.status);
    return response.data;
  } catch (error) {
    console.error('Error fetching recent projects:', error);
    throw error;
  }
};

// Get archived projects (older than 24h) with optional filters
export const getArchivedProjects = async (params = {}) => {
  try {
    const response = await api.get('/projects/archive', { params });
    return response.data;
  } catch (error) {
    console.error('Error fetching archived projects:', error);
    throw error;
  }
};

// Get scraper status
export const getScraperStatus = async () => {
  try {
    const response = await api.get('/status');
    return response.data;
  } catch (error) {
    console.error('Error fetching scraper status:', error);
    throw error;
  }
};

// Trigger a new scrape
export const triggerScrape = async (options = {}) => {
  try {
    const response = await api.post('/scrape', options);
    return response.data;
  } catch (error) {
    console.error('Error triggering scrape:', error);
    throw error;
  }
};

// Get new projects
export const getNewProjects = async () => {
  try {
    const response = await api.get('/new-projects');
    return response.data;
  } catch (error) {
    console.error('Error fetching new projects:', error);
    throw error;
  }
};

// Mark projects as seen
export const markProjectsAsSeen = async (projectIds) => {
  try {
    const response = await api.post('/mark-projects-seen', projectIds);
    return response.data;
  } catch (error) {
    console.error('Error marking projects as seen:', error);
    throw error;
  }
};

// Get email configuration
export const getEmailConfig = async () => {
  try {
    const response = await api.get('/email/config');
    return response.data;
  } catch (error) {
    console.error('Error fetching email configuration:', error);
    throw error;
  }
};

// Test email configuration
export const testEmailConfig = async (recipient = null) => {
  try {
    const requestData = {};
    if (recipient) {
      requestData.email = recipient;
    }
    
    const response = await api.post('/email/test', requestData);
    return response.data;
  } catch (error) {
    console.error('Error testing email configuration:', error);
    throw error;
  }
};

// Get scheduler configuration
export const getSchedulerConfig = async () => {
  try {
    const response = await api.get('/scheduler-config');
    return response.data;
  } catch (error) {
    console.error('Error fetching scheduler configuration:', error);
    throw error;
  }
};

// Set email configuration
export const setEmailConfig = async (config) => {
  try {
    const response = await api.post('/email/config', config);
    return response.data;
  } catch (error) {
    console.error('Error setting email configuration:', error);
    throw error;
  }
};

// Set scheduler configuration
export const setSchedulerConfig = async (config) => {
  try {
    const response = await api.post('/scheduler-config', config);
    return response.data;
  } catch (error) {
    console.error('Error setting scheduler configuration:', error);
    throw error;
  }
};

// Get a single project by ID
export const getProjectById = async (id) => {
  try {
    const response = await api.get(`/projects/${id}`);
    return response.data;
  } catch (error) {
    console.error(`Error fetching project with ID ${id}:`, error);
    throw error;
  }
};

// Helper function to manage favorites in localStorage
export const favoritesManager = {
  // Get all favorites
  getFavorites: () => {
    try {
      return JSON.parse(localStorage.getItem('favorites')) || [];
    } catch (error) {
      console.error('Error getting favorites from localStorage:', error);
      return [];
    }
  },
  
  // Add a project to favorites
  addFavorite: (project) => {
    try {
      const favorites = favoritesManager.getFavorites();
      // Check if project is already in favorites
      if (!favorites.some(fav => fav.id === project.id)) {
        favorites.push(project);
        localStorage.setItem('favorites', JSON.stringify(favorites));
      }
      return favorites;
    } catch (error) {
      console.error('Error adding favorite to localStorage:', error);
      return [];
    }
  },
  
  // Remove a project from favorites
  removeFavorite: (projectId) => {
    try {
      let favorites = favoritesManager.getFavorites();
      favorites = favorites.filter(fav => fav.id !== projectId);
      localStorage.setItem('favorites', JSON.stringify(favorites));
      return favorites;
    } catch (error) {
      console.error('Error removing favorite from localStorage:', error);
      return [];
    }
  },
  
  // Check if a project is in favorites
  isFavorite: (projectId) => {
    try {
      const favorites = favoritesManager.getFavorites();
      return favorites.some(fav => fav.id === projectId);
    } catch (error) {
      console.error('Error checking if project is favorite:', error);
      return false;
    }
  }
};

export default {
  getProjects,
  getProjectById,
  getScraperStatus,
  triggerScrape,
  getNewProjects,
  markProjectsAsSeen,
  getEmailConfig,
  setEmailConfig,
  getSchedulerConfig,
  setSchedulerConfig,
  favoritesManager
};
