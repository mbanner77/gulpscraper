import React, { useState, useEffect, useRef } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
  Box,
  Paper,
  Divider,
  CircularProgress,
  Tabs,
  Tab,
  Chip,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Grid,
  Card,
  CardContent,
  Stack,
  TextField,
  MenuItem,
  FormControl,
  InputLabel,
  Select,
  IconButton,
  Tooltip,
  Badge,
  Alert,
  Collapse
} from '@mui/material';
import {
  Close as CloseIcon,
  Refresh as RefreshIcon,
  Search as SearchIcon,
  Clear as ClearIcon,
  ExpandMore as ExpandMoreIcon,
  FilterList as FilterIcon,
  KeyboardArrowDown as ArrowDownIcon,
  KeyboardArrowRight as ArrowRightIcon,
  Schedule as ScheduleIcon,
  CheckCircle as SuccessIcon,
  Error as ErrorIcon,
  Info as InfoIcon,
  Warning as WarningIcon
} from '@mui/icons-material';
import WebIcon from '@mui/icons-material/Web';
import EmailIcon from '@mui/icons-material/Email';
import FilterListIcon from '@mui/icons-material/FilterList';
import ClearIcon from '@mui/icons-material/Clear';
import SearchIcon from '@mui/icons-material/Search';
import LinkIcon from '@mui/icons-material/Link';
import MemoryIcon from '@mui/icons-material/Memory';
import SpeedIcon from '@mui/icons-material/Speed';
import { formatDate } from '../utils/dateUtils';
import { getScraperLogs } from '../services/api';

const ScraperDetailsDialog = ({ open, onClose }) => {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [filteredLogs, setFilteredLogs] = useState([]);
  const [error, setError] = useState('');
  const [tabValue, setTabValue] = useState(0);
  const [expandedItems, setExpandedItems] = useState(new Set());
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [autoRefreshInterval, setAutoRefreshInterval] = useState(null);
  const [currentSession, setCurrentSession] = useState(null);
  const [sessionFilter, setSessionFilter] = useState('all');
  const [availableSessions, setAvailableSessions] = useState([]);
  const [logStatus, setLogStatus] = useState(null);
  const [statistics, setStatistics] = useState(null);
  const [showFilters, setShowFilters] = useState(false);
  const [filters, setFilters] = useState({
    searchTerm: '',
    eventType: 'all',
    logLevel: 'all',
    timeRange: 'all',
    sessionId: 'all'
  });
  const [correlationIds, setCorrelationIds] = useState([]);
  const [logLevels, setLogLevels] = useState({});
  const scrollRef = useRef(null);

  // Calculate statistics from logs
  const calculateStatistics = (logs) => {
    if (!logs || logs.length === 0) return null;
    
    // Initialize statistics object
    const stats = {
      totalEvents: logs.length,
      eventTypes: {},
      projectsFound: 0,
      newProjects: 0,
      uniqueProjects: 0,
      pagesScraped: 0,
      errors: 0,
      lastScrapeTime: null,
      scrapeDuration: null,
      browserType: null,
      hasEmailNotifications: false
    };
    
    // Track scrape start and end times
    let scrapeStartTime = null;
    let scrapeEndTime = null;
    
    // Process each log entry
    logs.forEach(log => {
      // Count event types
      const eventType = log.event_type || 'unknown';
      stats.eventTypes[eventType] = (stats.eventTypes[eventType] || 0) + 1;
      
      // Check for errors
      if (eventType === 'error') {
        stats.errors++;
      }
      
      // Track scrape start time
      if (log.message === 'Starting scraper') {
        scrapeStartTime = new Date(log.timestamp);
      }
      
      // Track scrape completion
      if (log.message === 'Scraping completed successfully' && log.data) {
        scrapeEndTime = new Date(log.timestamp);
        stats.lastScrapeTime = log.timestamp;
        
        if (log.data.unique_projects_count) {
          stats.uniqueProjects = log.data.unique_projects_count;
        }
        
        if (log.data.new_projects_count) {
          stats.newProjects = log.data.new_projects_count;
        }
      }
      
      // Track projects found
      if (log.message && log.message.includes('Projects extracted from page') && log.data && log.data.count) {
        stats.projectsFound += log.data.count;
        stats.pagesScraped++;
      }
      
      // Track browser type
      if (log.message === 'Creating browser context' && log.data && log.data.browser_type) {
        stats.browserType = log.data.browser_type;
      }
      
      // Check for email notifications
      if (log.message === 'Attempting to send email notification') {
        stats.hasEmailNotifications = true;
      }
    });
    
    // Calculate scrape duration if we have both start and end times
    if (scrapeStartTime && scrapeEndTime) {
      stats.scrapeDuration = Math.round((scrapeEndTime - scrapeStartTime) / 1000); // in seconds
    }
    
    return stats;
  };
  
  // Handle filter changes
  const handleFilterChange = (field) => (event) => {
    setFilters(prev => ({
      ...prev,
      [field]: event.target.value
    }));
  };
  
  // Clear all filters
  const clearFilters = () => {
    setFilters({
      eventType: '',
      logLevel: '',
      correlationId: '',
      search: '',
      limit: 100
    });
  };
  
  // Enhanced fetch logs function with session tracking
  const fetchLogs = async () => {
    try {
      setLoading(true);
      setError('');
      
      // Fetch both logs and status in parallel
      const [logsData, statusData] = await Promise.all([
        getScraperLogs(),
        getLogStatus()
      ]);
      
      const logsArray = Array.isArray(logsData) ? logsData : logsData.logs || [];
      setLogs(logsArray);
      setLogStatus(statusData);
      
      // Set current session if active
      if (statusData.current_session && statusData.current_session.active) {
        setCurrentSession(statusData.current_session.session_id);
      }
      
      // Extract unique session IDs for filter dropdown
      const uniqueSessions = [...new Set(
        logsArray
          .map(log => log.session_id)
          .filter(id => id)
      )];
      setAvailableSessions(uniqueSessions);
      
      // Extract unique correlation IDs for filter dropdown
      const uniqueCorrelationIds = [...new Set(
        logsArray
          .map(log => log.correlation_id)
          .filter(id => id)
      )];
      setCorrelationIds(uniqueCorrelationIds);
      
      // Calculate statistics
      setStatistics(calculateStatistics(logsArray));
      
    } catch (error) {
      console.error('Error fetching logs:', error);
      setError('Fehler beim Laden der Logs: ' + error.message);
    } finally {
      setLoading(false);
    }
  };
  
  // Fetch logs when the dialog opens or filters change
  useEffect(() => {
    if (open) {
      fetchLogs();
    }
  }, [open, filters.eventType, filters.logLevel, filters.sessionId]);
  
  // Debounce search input
  useEffect(() => {
    if (!open) return;
    
    const handler = setTimeout(() => {
      fetchLogs();
    }, 500);
    
    return () => clearTimeout(handler);
  }, [filters.searchTerm, open]);
  
  // Auto-refresh when current session is active
  useEffect(() => {
    if (!open || !autoRefresh) return;
    
    const interval = setInterval(() => {
      if (currentSession) {
        fetchLogs();
      }
    }, 3000); // Refresh every 3 seconds during active session
    
    setAutoRefreshInterval(interval);
    
    return () => {
      if (interval) {
        clearInterval(interval);
      }
    };
  }, [open, autoRefresh, currentSession]);
  
  // Filter logs based on current filters
  useEffect(() => {
    let filtered = logs;
    
    // Search term filter
    if (filters.searchTerm) {
      const searchLower = filters.searchTerm.toLowerCase();
      filtered = filtered.filter(log => 
        log.message?.toLowerCase().includes(searchLower) ||
        log.event_type?.toLowerCase().includes(searchLower) ||
        log.session_id?.toLowerCase().includes(searchLower)
      );
    }
    
    // Event type filter
    if (filters.eventType !== 'all') {
      filtered = filtered.filter(log => log.event_type === filters.eventType);
    }
    
    // Log level filter
    if (filters.logLevel !== 'all') {
      filtered = filtered.filter(log => log.log_level === filters.logLevel);
    }
    
    // Session filter
    if (filters.sessionId !== 'all') {
      filtered = filtered.filter(log => log.session_id === filters.sessionId);
    }
    
    setFilteredLogs(filtered);
  }, [logs, filters]);
  
  // Handle tab change
  const handleTabChange = (event, newValue) => {
    setTabValue(newValue);
  };
  
  // Get icon for log event type
  const getEventIcon = (eventType) => {
    switch (eventType.toLowerCase()) {
      case 'info':
        return <InfoIcon color="info" />;
      case 'warning':
        return <WarningIcon color="warning" />;
      case 'error':
        return <ErrorIcon color="error" />;
      case 'success':
        return <CheckCircleIcon color="success" />;
      default:
        return <InfoIcon />;
    }
  };
  
  // Format log timestamp
  const formatLogTime = (timestamp) => {
    if (!timestamp) return '';
    try {
      return formatDate(timestamp, true);
    } catch (err) {
      return timestamp;
    }
  };
  
  // Render JSON data in a readable format
  const renderJsonData = (data) => {
    if (!data) return null;
    
    try {
      const formattedData = typeof data === 'string' ? JSON.parse(data) : data;
      
      return (
        <Box 
          sx={{ 
            bgcolor: 'background.paper', 
            p: 1, 
            borderRadius: 1, 
            maxHeight: '200px', 
            overflow: 'auto',
            fontFamily: 'monospace',
            fontSize: '0.8rem'
          }}
        >
          <pre>{JSON.stringify(formattedData, null, 2)}</pre>
        </Box>
      );
    } catch (err) {
      return <Typography variant="body2">{String(data)}</Typography>;
    }
  };
  
  return (
    <Dialog 
      open={open} 
      onClose={onClose} 
      maxWidth="md" 
      fullWidth
      scroll="paper"
    >
      <DialogTitle>
        <Typography variant="h5">Scraper Details</Typography>
        <Typography variant="subtitle2" color="text.secondary">
          Detaillierte Informationen über den Scraper-Prozess
        </Typography>
      </DialogTitle>
      
      <Divider />
      
      <DialogContent>
        <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Tabs value={tabValue} onChange={handleTabChange}>
              <Tab label="Logs" />
              <Tab label="Statistiken" />
            </Tabs>
            
            {tabValue === 0 && (
              <Tooltip title={showFilters ? "Filter ausblenden" : "Filter anzeigen"}>
                <IconButton onClick={() => setShowFilters(!showFilters)}>
                  <FilterListIcon />
                </IconButton>
              </Tooltip>
            )}
          </Box>
          
          {/* Filters Panel */}
          {tabValue === 0 && showFilters && (
            <Paper variant="outlined" sx={{ p: 2, mb: 2, mt: 1 }}>
              <Grid container spacing={2} alignItems="center">
                <Grid item xs={12} md={3}>
                  <FormControl fullWidth size="small">
                    <InputLabel>Event-Typ</InputLabel>
                    <Select
                      value={filters.eventType}
                      onChange={(e) => setFilters(prev => ({ ...prev, eventType: e.target.value }))}
                      label="Event-Typ"
                    >
                      <MenuItem value="all">Alle</MenuItem>
                      <MenuItem value="info">Info</MenuItem>
                      <MenuItem value="success">Success</MenuItem>
                      <MenuItem value="warning">Warning</MenuItem>
                      <MenuItem value="error">Error</MenuItem>
                    </Select>
                  </FormControl>
                </Grid>
                
                <Grid item xs={12} md={3}>
                  <FormControl fullWidth size="small">
                    <InputLabel>Log-Level</InputLabel>
                    <Select
                      value={filters.logLevel}
                      onChange={(e) => setFilters(prev => ({ ...prev, logLevel: e.target.value }))}
                      label="Log-Level"
                    >
                      <MenuItem value="all">Alle</MenuItem>
                      <MenuItem value="DEBUG">DEBUG</MenuItem>
                      <MenuItem value="INFO">INFO</MenuItem>
                      <MenuItem value="WARNING">WARNING</MenuItem>
                      <MenuItem value="ERROR">ERROR</MenuItem>
                      <MenuItem value="CRITICAL">CRITICAL</MenuItem>
                    </Select>
                  </FormControl>
                </Grid>
                
                <Grid item xs={12} md={3}>
                  <FormControl fullWidth size="small">
                    <InputLabel>Session</InputLabel>
                    <Select
                      value={filters.sessionId}
                      onChange={(e) => setFilters(prev => ({ ...prev, sessionId: e.target.value }))}
                      label="Session"
                    >
                      <MenuItem value="all">Alle Sessions</MenuItem>
                      {currentSession && (
                        <MenuItem value={currentSession}>
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            <Badge color="success" variant="dot" />
                            Aktuelle Session
                          </Box>
                        </MenuItem>
                      )}
                      {availableSessions.filter(id => id !== currentSession).map((sessionId) => (
                        <MenuItem key={sessionId} value={sessionId}>
                          {sessionId.substring(0, 20)}...
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                </Grid>
                
                <Grid item xs={12} md={3}>
                  <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                    <Button
                      size="small"
                      variant={autoRefresh ? "contained" : "outlined"}
                      color={currentSession ? "success" : "primary"}
                      onClick={() => setAutoRefresh(!autoRefresh)}
                      disabled={!currentSession}
                    >
                      Auto-Refresh
                    </Button>
                    <Button
                      size="small"
                      onClick={() => setFilters({
                        searchTerm: '',
                        eventType: 'all',
                        logLevel: 'all',
                        sessionId: 'all'
                      })}
                    >
                      Reset
                    </Button>
                  </Box>
                </Grid>
                
                <Grid item xs={12}>
                  <TextField
                    fullWidth
                    size="small"
                    label="Suche in Logs"
                    value={filters.search}
                    onChange={handleFilterChange('search')}
                    InputProps={{
                      startAdornment: <SearchIcon color="action" sx={{ mr: 1 }} />,
                      endAdornment: filters.search ? (
                        <IconButton size="small" onClick={() => setFilters(prev => ({ ...prev, search: '' }))}>
                          <ClearIcon fontSize="small" />
                        </IconButton>
                      ) : null
                    }}
                  />
                </Grid>
                
                <Grid item xs={12} sx={{ display: 'flex', justifyContent: 'flex-end' }}>
                  <Button 
                    variant="outlined" 
                    size="small" 
                    startIcon={<ClearIcon />}
                    onClick={clearFilters}
                  >
                    Filter zurücksetzen
                  </Button>
                </Grid>
              </Grid>
            </Paper>
          )}
        </Box>
        
        {/* Logs Tab */}
        <Box role="tabpanel" hidden={tabValue !== 0}>
          {loading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
              <CircularProgress />
            </Box>
          ) : error ? (
            <Box sx={{ p: 2 }}>
              <Typography color="error">{error}</Typography>
              <Button 
                variant="outlined" 
                color="primary" 
                onClick={fetchLogs} 
                sx={{ mt: 2 }}
              >
                Erneut versuchen
              </Button>
            </Box>
          ) : logs.length === 0 ? (
            <Box sx={{ p: 2 }}>
              <Typography>Keine Logs verfügbar.</Typography>
            </Box>
          ) : (
            <List sx={{ width: '100%' }}>
              {logs.map((log, index) => (
                <Accordion key={index} sx={{ mb: 1 }}>
                  <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                    <Grid container alignItems="center" spacing={1}>
                      <Grid item>
                        {getEventIcon(log.event_type)}
                      </Grid>
                      <Grid item xs>
                        <Typography variant="body1">
                          {log.message}
                        </Typography>
                      </Grid>
                      <Grid item>
                        <Stack direction="row" spacing={1}>
                          <Chip 
                            label={log.event_type} 
                            size="small" 
                            color={
                              log.event_type === 'error' ? 'error' : 
                              log.event_type === 'warning' ? 'warning' : 
                              log.event_type === 'success' ? 'success' : 
                              'default'
                            }
                            variant="outlined"
                          />
                          {log.log_level && (
                            <Chip 
                              label={log.log_level} 
                              size="small" 
                              color={
                                log.log_level === 'ERROR' ? 'error' : 
                                log.log_level === 'WARNING' ? 'warning' : 
                                log.log_level === 'CRITICAL' ? 'error' : 
                                log.log_level === 'DEBUG' ? 'info' : 
                                'default'
                              }
                            />
                          )}
                        </Stack>
                      </Grid>
                      <Grid item>
                        <Typography variant="caption" color="text.secondary">
                          {formatLogTime(log.timestamp)}
                        </Typography>
                      </Grid>
                    </Grid>
                  </AccordionSummary>
                  <AccordionDetails>
                    <Grid container spacing={2}>
                      {/* Correlation ID */}
                      {log.correlation_id && (
                        <Grid item xs={12}>
                          <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                            <LinkIcon fontSize="small" sx={{ mr: 1 }} color="primary" />
                            <Typography variant="body2" color="text.secondary">
                              Correlation ID: 
                              <Chip 
                                label={log.correlation_id} 
                                size="small" 
                                sx={{ ml: 1 }}
                                onClick={() => {
                                  setFilters(prev => ({ ...prev, correlationId: log.correlation_id }));
                                  setShowFilters(true);
                                }}
                              />
                            </Typography>
                          </Box>
                        </Grid>
                      )}
                      
                      {/* Performance Metrics */}
                      {log.performance && (
                        <Grid item xs={12} md={6}>
                          <Paper variant="outlined" sx={{ p: 1 }}>
                            <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                              <SpeedIcon fontSize="small" sx={{ mr: 1 }} color="primary" />
                              <Typography variant="subtitle2">
                                Performance Metrics
                              </Typography>
                            </Box>
                            {renderJsonData(log.performance)}
                          </Paper>
                        </Grid>
                      )}
                      
                      {/* Environment Info */}
                      {log.environment && (
                        <Grid item xs={12} md={6}>
                          <Paper variant="outlined" sx={{ p: 1 }}>
                            <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                              <WebIcon fontSize="small" sx={{ mr: 1 }} color="primary" />
                              <Typography variant="subtitle2">
                                Environment
                              </Typography>
                            </Box>
                            {renderJsonData(log.environment)}
                          </Paper>
                        </Grid>
                      )}
                      
                      {/* Tags */}
                      {log.tags && log.tags.length > 0 && (
                        <Grid item xs={12}>
                          <Box sx={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 1 }}>
                            {log.tags.map((tag, tagIndex) => (
                              <Chip 
                                key={tagIndex}
                                label={tag} 
                                size="small" 
                                variant="outlined"
                                onClick={() => {
                                  setFilters(prev => ({ ...prev, tag }));
                                  setShowFilters(true);
                                }}
                              />
                            ))}
                          </Box>
                        </Grid>
                      )}
                      
                      {/* Main Data */}
                      {log.data && (
                        <Grid item xs={12}>
                          <Typography variant="subtitle2" gutterBottom>
                            Details:
                          </Typography>
                          {renderJsonData(log.data)}
                        </Grid>
                      )}
                    </Grid>
                  </AccordionDetails>
                </Accordion>
              ))}
            </List>
          )}
        </Box>
        
        {/* Statistics Tab */}
        <Box role="tabpanel" hidden={tabValue !== 1}>
          {loading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
              <CircularProgress />
            </Box>
          ) : error ? (
            <Box sx={{ p: 2 }}>
              <Typography color="error">{error}</Typography>
              <Button 
                variant="outlined" 
                color="primary" 
                onClick={fetchLogs} 
                sx={{ mt: 2 }}
              >
                Erneut versuchen
              </Button>
            </Box>
          ) : !statistics ? (
            <Box sx={{ p: 2 }}>
              <Typography>Keine Statistiken verfügbar.</Typography>
            </Box>
          ) : (
            <>
              {/* Last Scrape Summary */}
              <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                  <AccessTimeIcon sx={{ mr: 1 }} color="primary" />
                  <Typography variant="h6">
                    Letzte Scraper-Ausführung
                  </Typography>
                </Box>
                <Divider sx={{ my: 1 }} />
                <Grid container spacing={2}>
                  <Grid item xs={12} md={6}>
                    <Typography variant="body2" color="text.secondary">
                      Letzte Ausführung:
                    </Typography>
                    <Typography variant="body1">
                      {statistics.lastScrapeTime ? formatLogTime(statistics.lastScrapeTime) : 'Unbekannt'}
                    </Typography>
                  </Grid>
                  <Grid item xs={12} md={6}>
                    <Typography variant="body2" color="text.secondary">
                      Dauer:
                    </Typography>
                    <Typography variant="body1">
                      {statistics.scrapeDuration ? `${statistics.scrapeDuration} Sekunden` : 'Unbekannt'}
                    </Typography>
                  </Grid>
                </Grid>
              </Paper>
              
              {/* Project Statistics */}
              <Grid container spacing={2} sx={{ mb: 2 }}>
                <Grid item xs={12} md={4}>
                  <Card variant="outlined" sx={{ height: '100%' }}>
                    <CardContent>
                      <Typography variant="h6" color="primary" gutterBottom>
                        {statistics.projectsFound}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        Gefundene Projekte
                      </Typography>
                    </CardContent>
                  </Card>
                </Grid>
                <Grid item xs={12} md={4}>
                  <Card variant="outlined" sx={{ height: '100%' }}>
                    <CardContent>
                      <Typography variant="h6" color="primary" gutterBottom>
                        {statistics.uniqueProjects}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        Eindeutige Projekte
                      </Typography>
                    </CardContent>
                  </Card>
                </Grid>
                <Grid item xs={12} md={4}>
                  <Card variant="outlined" sx={{ height: '100%' }}>
                    <CardContent>
                      <Typography variant="h6" color="success.main" gutterBottom>
                        {statistics.newProjects}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        Neue Projekte
                      </Typography>
                    </CardContent>
                  </Card>
                </Grid>
              </Grid>
              
              {/* Technical Details */}
              <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                  <WebIcon sx={{ mr: 1 }} color="primary" />
                  <Typography variant="h6">
                    Technische Details
                  </Typography>
                </Box>
                <Divider sx={{ my: 1 }} />
                <Grid container spacing={2}>
                  <Grid item xs={12} md={4}>
                    <Typography variant="body2" color="text.secondary">
                      Browser:
                    </Typography>
                    <Typography variant="body1">
                      {statistics.browserType || 'Unbekannt'}
                    </Typography>
                  </Grid>
                  <Grid item xs={12} md={4}>
                    <Typography variant="body2" color="text.secondary">
                      Gescrapte Seiten:
                    </Typography>
                    <Typography variant="body1">
                      {statistics.pagesScraped}
                    </Typography>
                  </Grid>
                  <Grid item xs={12} md={4}>
                    <Typography variant="body2" color="text.secondary">
                      E-Mail-Benachrichtigungen:
                    </Typography>
                    <Typography variant="body1">
                      {statistics.hasEmailNotifications ? (
                        <Box sx={{ display: 'flex', alignItems: 'center' }}>
                          <CheckCircleIcon color="success" fontSize="small" sx={{ mr: 0.5 }} />
                          Aktiviert
                        </Box>
                      ) : (
                        <Box sx={{ display: 'flex', alignItems: 'center' }}>
                          <InfoIcon color="disabled" fontSize="small" sx={{ mr: 0.5 }} />
                          Nicht verwendet
                        </Box>
                      )}
                    </Typography>
                  </Grid>
                </Grid>
              </Paper>
              
              {/* Event Statistics */}
              <Paper variant="outlined" sx={{ p: 2 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                  <BarChartIcon sx={{ mr: 1 }} color="primary" />
                  <Typography variant="h6">
                    Event-Statistiken
                  </Typography>
                </Box>
                <Divider sx={{ my: 1 }} />
                <Grid container spacing={2}>
                  <Grid item xs={12} md={3}>
                    <Card variant="outlined" sx={{ bgcolor: 'info.light', color: 'info.contrastText' }}>
                      <CardContent>
                        <Typography variant="h6" gutterBottom>
                          {statistics.eventTypes.info || 0}
                        </Typography>
                        <Typography variant="body2">
                          Info Events
                        </Typography>
                      </CardContent>
                    </Card>
                  </Grid>
                  <Grid item xs={12} md={3}>
                    <Card variant="outlined" sx={{ bgcolor: 'success.light', color: 'success.contrastText' }}>
                      <CardContent>
                        <Typography variant="h6" gutterBottom>
                          {statistics.eventTypes.success || 0}
                        </Typography>
                        <Typography variant="body2">
                          Success Events
                        </Typography>
                      </CardContent>
                    </Card>
                  </Grid>
                  <Grid item xs={12} md={3}>
                    <Card variant="outlined" sx={{ bgcolor: 'warning.light', color: 'warning.contrastText' }}>
                      <CardContent>
                        <Typography variant="h6" gutterBottom>
                          {statistics.eventTypes.warning || 0}
                        </Typography>
                        <Typography variant="body2">
                          Warning Events
                        </Typography>
                      </CardContent>
                    </Card>
                  </Grid>
                  <Grid item xs={12} md={3}>
                    <Card variant="outlined" sx={{ bgcolor: 'error.light', color: 'error.contrastText' }}>
                      <CardContent>
                        <Typography variant="h6" gutterBottom>
                          {statistics.eventTypes.error || 0}
                        </Typography>
                        <Typography variant="body2">
                          Error Events
                        </Typography>
                      </CardContent>
                    </Card>
                  </Grid>
                </Grid>
              </Paper>
            </>
          )}
        </Box>
      </DialogContent>
      
      <DialogActions>
        {!loading && (
          <Button 
            onClick={fetchLogs} 
            color="primary"
            startIcon={<RefreshIcon />}
          >
            Aktualisieren
          </Button>
        )}
        <Button onClick={onClose} color="primary">
          Schließen
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default ScraperDetailsDialog;
