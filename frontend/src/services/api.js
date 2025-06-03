import axios from 'axios';

// Use environment variable for API URL with fallback for local development
const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

// Create axios instance with base URL
const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Get all projects with optional filters
export const getProjects = async (params = {}) => {
  try {
    const response = await api.get('/projects', { params });
    return response.data;
  } catch (error) {
    console.error('Error fetching projects:', error);
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
    const response = await api.get('/email-config');
    return response.data;
  } catch (error) {
    console.error('Error fetching email configuration:', error);
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
    const response = await api.post('/email-config', config);
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
