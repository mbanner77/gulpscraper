/**
 * AI Configuration Utilities
 * Provides functions to manage AI configuration settings
 */

// Default AI configuration
const defaultConfig = {
  enabled: true,
  apiKey: '',
  defaultModel: 'google/flan-t5-small',
  autoAnalyze: false,
  maxTokens: 100
};

/**
 * Initialize AI configuration
 * Sets default configuration if none exists
 */
export const initAIConfig = () => {
  try {
    const savedConfig = localStorage.getItem('aiConfig');
    if (!savedConfig) {
      localStorage.setItem('aiConfig', JSON.stringify(defaultConfig));
      console.log('AI configuration initialized with defaults');
    }
  } catch (err) {
    console.error('Error initializing AI configuration:', err);
  }
};

/**
 * Get current AI configuration
 * @returns {Object} Current AI configuration
 */
export const getAIConfig = () => {
  try {
    const savedConfig = localStorage.getItem('aiConfig');
    if (savedConfig) {
      return JSON.parse(savedConfig);
    }
    return defaultConfig;
  } catch (err) {
    console.error('Error getting AI configuration:', err);
    return defaultConfig;
  }
};

/**
 * Save AI configuration
 * @param {Object} config - AI configuration to save
 * @returns {boolean} Success status
 */
export const saveAIConfig = (config) => {
  try {
    localStorage.setItem('aiConfig', JSON.stringify(config));
    return true;
  } catch (err) {
    console.error('Error saving AI configuration:', err);
    return false;
  }
};

// Initialize AI configuration on module import
initAIConfig();
