/**
 * Utility functions for date formatting
 */

/**
 * Format a date string to a localized format
 * @param {string} dateString - ISO date string
 * @returns {string} Formatted date string
 */
export const formatDate = (dateString) => {
  if (!dateString) return 'Unbekannt';
  
  try {
    const date = new Date(dateString);
    return date.toLocaleDateString('de-DE', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    });
  } catch (error) {
    console.error('Error formatting date:', error);
    return 'Ungültiges Datum';
  }
};

/**
 * Check if a date is within the last 24 hours
 * @param {string} dateString - ISO date string
 * @returns {boolean} True if date is within last 24 hours
 */
export const isRecent = (dateString) => {
  if (!dateString) return false;
  
  try {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now - date;
    const diffHours = diffMs / (1000 * 60 * 60);
    
    return diffHours < 24;
  } catch (error) {
    console.error('Error checking if date is recent:', error);
    return false;
  }
};
