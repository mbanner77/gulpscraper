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
  AlertTitle,
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
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  Info as InfoIcon,
  Warning as WarningIcon,
  AccessTime as AccessTimeIcon,
  BarChart as BarChartIcon
} from '@mui/icons-material';
import WebIcon from '@mui/icons-material/Web';
import EmailIcon from '@mui/icons-material/Email';
import FilterListIcon from '@mui/icons-material/FilterList';
import LinkIcon from '@mui/icons-material/Link';
import MemoryIcon from '@mui/icons-material/Memory';
import SpeedIcon from '@mui/icons-material/Speed';
import FavoriteIcon from '@mui/icons-material/Favorite';
import TimelineIcon from '@mui/icons-material/Timeline';
import BuildIcon from '@mui/icons-material/Build';
import AssessmentIcon from '@mui/icons-material/Assessment';
import { formatDate } from '../utils/dateUtils';
import { getScraperLogs, getLogStatus, getSessionLogs, getErrorAnalysis } from '../services/api';

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
  const [errorAnalysis, setErrorAnalysis] = useState(null);
  const [healthIndicators, setHealthIndicators] = useState(null);
  const [comprehensiveStats, setComprehensiveStats] = useState(null);
  const [diagnosticRecommendations, setDiagnosticRecommendations] = useState([]);
  const [performanceIssues, setPerformanceIssues] = useState([]);
  const [errorTimeline, setErrorTimeline] = useState([]);
  const [systemMetrics, setSystemMetrics] = useState(null);
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
      errorTypes: {},
      criticalErrors: 0,
      lastScrapeTime: null,
      scrapeDuration: null,
      browserType: null,
      hasEmailNotifications: false,
      correlationIds: new Set(),
      sessionIds: new Set(),
      environmentInfo: {},
      playwrightErrors: 0,
      networkErrors: 0,
      navigationErrors: 0,
      renderEnvironment: false
    };
    
    // Track scrape start and end times
    let scrapeStartTime = null;
    let scrapeEndTime = null;
    
    // Process each log entry
    logs.forEach(log => {
      // Count event types
      const eventType = log.event_type || 'unknown';
      stats.eventTypes[eventType] = (stats.eventTypes[eventType] || 0) + 1;
      
      // Track correlation IDs
      if (log.correlation_id) {
        stats.correlationIds.add(log.correlation_id);
      }
      
      // Track session IDs
      if (log.session_id) {
        stats.sessionIds.add(log.session_id);
      }
      
      // Check for errors
      if (eventType === 'error') {
        stats.errors++;
        
        // Analyze error types
        if (log.data) {
          if (log.data.error_type) {
            stats.errorTypes[log.data.error_type] = (stats.errorTypes[log.data.error_type] || 0) + 1;
          }
          
          // Check for critical errors
          if (log.message.includes('Critical error') || log.tags?.includes('critical_error')) {
            stats.criticalErrors++;
          }
          
          // Categorize specific error types
          if (log.tags?.includes('playwright') || log.message.includes('Playwright')) {
            stats.playwrightErrors++;
          }
          
          if (log.tags?.includes('network') || log.message.includes('network')) {
            stats.networkErrors++;
          }
          
          if (log.tags?.includes('navigation') || log.message.includes('navigation')) {
            stats.navigationErrors++;
          }
        }
      }
      
      // Check for render environment
      if (log.data?.is_cloud_env || log.tags?.includes('render')) {
        stats.renderEnvironment = true;
      }
      
      // Extract environment info
      if (log.data) {
        if (log.data.headless !== undefined) {
          stats.environmentInfo.headless = log.data.headless;
        }
        if (log.data.timeout_ms) {
          stats.environmentInfo.timeout_ms = log.data.timeout_ms;
        }
        if (log.data.use_real_scraper !== undefined) {
          stats.environmentInfo.use_real_scraper = log.data.use_real_scraper;
        }
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
      
      // Fetch logs, status, and error analysis in parallel
      const [logsData, statusData, errorAnalysisData] = await Promise.all([
        getScraperLogs().catch(err => ({ logs: [], count: 0, total_count: 0, stats: {} })),
        getLogStatus().catch(err => ({ health_indicators: {}, system_metrics: {}, comprehensive_stats: {} })),
        getErrorAnalysis(24).catch(err => ({ error_analysis: {}, diagnostic_recommendations: [], performance_issues: [], error_timeline: [] }))
      ]);
      
      const logsArray = Array.isArray(logsData) ? logsData : logsData.logs || [];
      setLogs(logsArray);
      setLogStatus(statusData);
      
      // Set current session if active
      if (statusData?.current_session?.active) {
        setCurrentSession(statusData.current_session.session_id);
      }
      
      // Extract unique session IDs for filter dropdown with null safety
      const uniqueSessions = [...new Set(
        (logsArray || [])
          .map(log => log?.session_id)
          .filter(id => id && id !== null && id !== undefined)
      )];
      setAvailableSessions(uniqueSessions);
      
      // Extract unique correlation IDs for filter dropdown with null safety
      const uniqueCorrelationIds = [...new Set(
        (logsArray || [])
          .map(log => log?.correlation_id)
          .filter(id => id && id !== null && id !== undefined)
      )];
      setCorrelationIds(uniqueCorrelationIds);
      
      // Calculate statistics with null safety
      setStatistics(calculateStatistics(logsArray || []));
      
      // Process enhanced status data with null safety
      if (statusData?.comprehensive_statistics) {
        setComprehensiveStats(statusData.comprehensive_statistics);
      }
      
      if (statusData?.health_indicators) {
        setHealthIndicators(statusData.health_indicators);
      }
      
      if (statusData?.system_metrics) {
        setSystemMetrics(statusData.system_metrics);
      }
      
      // Process error analysis data with null safety
      if (errorAnalysisData && (errorAnalysisData.status === 'success' || errorAnalysisData.analysis)) {
        const analysis = errorAnalysisData.analysis || errorAnalysisData;
        setErrorAnalysis(analysis || {});
        
        if (analysis?.diagnostic_recommendations && Array.isArray(analysis.diagnostic_recommendations)) {
          setDiagnosticRecommendations(analysis.diagnostic_recommendations);
        }
        
        if (analysis?.performance_issues && Array.isArray(analysis.performance_issues)) {
          setPerformanceIssues(analysis.performance_issues);
        }
        
        if (analysis?.error_timeline && Array.isArray(analysis.error_timeline)) {
          setErrorTimeline(analysis.error_timeline);
        }
      }
      
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
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Box>
            <Typography variant="h5">Scraper Details</Typography>
            <Typography variant="subtitle2" color="text.secondary">
              Detaillierte Informationen über den Scraper-Prozess
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
            {currentSession && (
              <Chip
                icon={<Badge color="success" variant="dot" />}
                label={`Aktive Session: ${currentSession.substring(0, 12)}...`}
                color="success"
                variant="outlined"
                size="small"
              />
            )}
            {logStatus && (
              <Chip
                label={`${filteredLogs.length} / ${logs.length} Logs`}
                color="primary"
                variant="outlined"
                size="small"
              />
            )}
          </Box>
        </Box>
      </DialogTitle>
      
      <Divider />
      
      <DialogContent>
        <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Tabs value={tabValue} onChange={handleTabChange}>
              <Tab label="Logs" />
              <Tab label="Statistiken" />
              <Tab label="System-Health" />
              <Tab label="Fehleranalyse" />
              <Tab label="Diagnose" />
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
                    label="Suche in Logs (Message, Event-Typ, Session-ID)"
                    value={filters.searchTerm}
                    onChange={(e) => setFilters(prev => ({ ...prev, searchTerm: e.target.value }))}
                    InputProps={{
                      startAdornment: <SearchIcon color="action" sx={{ mr: 1 }} />,
                      endAdornment: filters.searchTerm ? (
                        <IconButton size="small" onClick={() => setFilters(prev => ({ ...prev, searchTerm: '' }))}>
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
              {filteredLogs.map((log, index) => (
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
                        {log.session_id && (
                          <Typography variant="caption" color="text.secondary">
                            Session: {log.session_id}
                          </Typography>
                        )}
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
                      {/* Session and Correlation Information */}
                      <Grid item xs={12}>
                        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 1 }}>
                          {log.correlation_id && (
                            <Chip
                              icon={<LinkIcon fontSize="small" />}
                              label={`Correlation: ${log.correlation_id.substring(0, 8)}...`}
                              size="small"
                              variant="outlined"
                              color="primary"
                              onClick={() => {
                                setFilters(prev => ({ ...prev, correlationId: log.correlation_id }));
                                setShowFilters(true);
                              }}
                              sx={{ cursor: 'pointer' }}
                            />
                          )}
                          {log.session_id && (
                            <Chip
                              label={`Session: ${log.session_id}`}
                              size="small"
                              variant="outlined"
                              color="info"
                            />
                          )}
                          {log.tags && log.tags.length > 0 && (
                            log.tags.map((tag, tagIndex) => (
                              <Chip
                                key={tagIndex}
                                label={tag}
                                size="small"
                                variant="outlined"
                                color="secondary"
                              />
                            ))
                          )}
                        </Box>
                      </Grid>
                      
                      {/* Error Details */}
                      {log.event_type === 'error' && log.data && (
                        <Grid item xs={12}>
                          <Paper variant="outlined" sx={{ p: 2, bgcolor: 'error.light', borderColor: 'error.main' }}>
                            <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                              <ErrorIcon fontSize="small" sx={{ mr: 1 }} color="error" />
                              <Typography variant="subtitle2" color="error">
                                Fehlerdetails
                              </Typography>
                            </Box>
                            
                            {log.data.error_type && (
                              <Typography variant="body2" sx={{ mb: 1 }}>
                                <strong>Fehlertyp:</strong> {log.data.error_type}
                              </Typography>
                            )}
                            
                            {log.data.error && (
                              <Typography variant="body2" sx={{ mb: 1 }}>
                                <strong>Fehlermeldung:</strong> {log.data.error}
                              </Typography>
                            )}
                            
                            {log.data.traceback && (
                              <Box sx={{ mt: 1 }}>
                                <Typography variant="body2" sx={{ mb: 1 }}>
                                  <strong>Traceback:</strong>
                                </Typography>
                                <Box
                                  sx={{
                                    bgcolor: 'background.paper',
                                    p: 1,
                                    borderRadius: 1,
                                    maxHeight: '200px',
                                    overflow: 'auto',
                                    fontFamily: 'monospace',
                                    fontSize: '0.75rem',
                                    whiteSpace: 'pre-wrap'
                                  }}
                                >
                                  {log.data.traceback}
                                </Box>
                              </Box>
                            )}
                          </Paper>
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
              
              {/* Error Analysis */}
              {(statistics.errors > 0 || statistics.criticalErrors > 0) && (
                <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>  
                  <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>  
                    <ErrorIcon sx={{ mr: 1 }} color="error" />  
                    <Typography variant="h6">  
                      Fehleranalyse  
                    </Typography>  
                  </Box>  
                  <Divider sx={{ my: 1 }} />  
                  <Grid container spacing={2}>  
                    <Grid item xs={12} md={3}>  
                      <Card variant="outlined" sx={{ bgcolor: 'error.light', color: 'error.contrastText' }}>  
                        <CardContent>  
                          <Typography variant="h6" gutterBottom>  
                            {statistics.errors}  
                          </Typography>  
                          <Typography variant="body2">  
                            Gesamt Fehler  
                          </Typography>  
                        </CardContent>  
                      </Card>  
                    </Grid>  
                    <Grid item xs={12} md={3}>  
                      <Card variant="outlined" sx={{ bgcolor: 'error.dark', color: 'error.contrastText' }}>  
                        <CardContent>  
                          <Typography variant="h6" gutterBottom>  
                            {statistics.criticalErrors}  
                          </Typography>  
                          <Typography variant="body2">  
                            Kritische Fehler  
                          </Typography>  
                        </CardContent>  
                      </Card>  
                    </Grid>  
                    <Grid item xs={12} md={3}>  
                      <Card variant="outlined" sx={{ bgcolor: 'warning.light', color: 'warning.contrastText' }}>  
                        <CardContent>  
                          <Typography variant="h6" gutterBottom>  
                            {statistics.playwrightErrors}  
                          </Typography>  
                          <Typography variant="body2">  
                            Browser-Fehler  
                          </Typography>  
                        </CardContent>  
                      </Card>  
                    </Grid>  
                    <Grid item xs={12} md={3}>  
                      <Card variant="outlined" sx={{ bgcolor: 'info.light', color: 'info.contrastText' }}>  
                        <CardContent>  
                          <Typography variant="h6" gutterBottom>  
                            {statistics.networkErrors + statistics.navigationErrors}  
                          </Typography>  
                          <Typography variant="body2">  
                            Netzwerk-Fehler  
                          </Typography>  
                        </CardContent>  
                      </Card>  
                    </Grid>  
                  </Grid>  
                  
                  {/* Error Types Details */}
                  {Object.keys(statistics.errorTypes).length > 0 && (
                    <Box sx={{ mt: 2 }}>  
                      <Typography variant="subtitle2" sx={{ mb: 1 }}>  
                        Fehlertypen:  
                      </Typography>  
                      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>  
                        {Object.entries(statistics.errorTypes).map(([errorType, count]) => (  
                          <Chip   
                            key={errorType}  
                            label={`${errorType}: ${count}`}  
                            size="small"  
                            color="error"  
                            variant="outlined"  
                          />  
                        ))}  
                      </Box>  
                    </Box>
                  )}
                </Paper>  
              )}
              
              {/* Environment Information */}
              <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>  
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>  
                  <MemoryIcon sx={{ mr: 1 }} color="primary" />  
                  <Typography variant="h6">  
                    Umgebungsdetails  
                  </Typography>  
                  {statistics.renderEnvironment && (
                    <Chip 
                      label="Render Cloud" 
                      size="small" 
                      color="primary" 
                      sx={{ ml: 1 }}
                    />
                  )}
                </Box>  
                <Divider sx={{ my: 1 }} />  
                <Grid container spacing={2}>  
                  <Grid item xs={12} md={4}>  
                    <Typography variant="body2" color="text.secondary">  
                      Korrelations-IDs:  
                    </Typography>  
                    <Typography variant="body1">  
                      {statistics.correlationIds.size}  
                    </Typography>  
                  </Grid>  
                  <Grid item xs={12} md={4}>  
                    <Typography variant="body2" color="text.secondary">  
                      Session-IDs:  
                    </Typography>  
                    <Typography variant="body1">  
                      {statistics.sessionIds.size}  
                    </Typography>  
                  </Grid>  
                  <Grid item xs={12} md={4}>  
                    <Typography variant="body2" color="text.secondary">  
                      Headless-Modus:  
                    </Typography>  
                    <Typography variant="body1">  
                      {statistics.environmentInfo.headless !== undefined 
                        ? (statistics.environmentInfo.headless ? 'Ja' : 'Nein') 
                        : 'Unbekannt'}  
                    </Typography>  
                  </Grid>  
                  <Grid item xs={12} md={4}>  
                    <Typography variant="body2" color="text.secondary">  
                      Timeout (ms):  
                    </Typography>  
                    <Typography variant="body1">  
                      {statistics.environmentInfo.timeout_ms || 'Standard'}  
                    </Typography>  
                  </Grid>  
                  <Grid item xs={12} md={4}>  
                    <Typography variant="body2" color="text.secondary">  
                      Echter Scraper:  
                    </Typography>  
                    <Typography variant="body1">  
                      {statistics.environmentInfo.use_real_scraper !== undefined 
                        ? (statistics.environmentInfo.use_real_scraper ? 'Aktiviert' : 'Deaktiviert') 
                        : 'Unbekannt'}  
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

        {/* System Health Tab */}
        <Box role="tabpanel" hidden={tabValue !== 2}>
          {loading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
              <CircularProgress />
            </Box>
          ) : (
            <>
              {/* Health Indicators */}
              {healthIndicators && (
                <Paper sx={{ p: 2, mb: 2 }}>
                  <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center' }}>
                    <FavoriteIcon sx={{ mr: 1, color: 'error.main' }} />
                    System Health Status
                  </Typography>
                  <Grid container spacing={2}>
                    <Grid item xs={12} md={3}>
                      <Card variant="outlined" sx={{ 
                        bgcolor: healthIndicators.memory_health === 'good' ? 'success.light' : 
                                healthIndicators.memory_health === 'warning' ? 'warning.light' : 'error.light',
                        color: healthIndicators.memory_health === 'good' ? 'success.contrastText' : 
                               healthIndicators.memory_health === 'warning' ? 'warning.contrastText' : 'error.contrastText'
                      }}>
                        <CardContent>
                          <Typography variant="h6" gutterBottom>
                            {healthIndicators.memory_health?.toUpperCase()}
                          </Typography>
                          <Typography variant="body2">
                            Memory Health
                          </Typography>
                        </CardContent>
                      </Card>
                    </Grid>
                    <Grid item xs={12} md={3}>
                      <Card variant="outlined" sx={{ 
                        bgcolor: healthIndicators.error_rate === 'good' ? 'success.light' : 
                                healthIndicators.error_rate === 'warning' ? 'warning.light' : 'error.light',
                        color: healthIndicators.error_rate === 'good' ? 'success.contrastText' : 
                               healthIndicators.error_rate === 'warning' ? 'warning.contrastText' : 'error.contrastText'
                      }}>
                        <CardContent>
                          <Typography variant="h6" gutterBottom>
                            {healthIndicators.error_rate?.toUpperCase()}
                          </Typography>
                          <Typography variant="body2">
                            Error Rate
                          </Typography>
                        </CardContent>
                      </Card>
                    </Grid>
                    <Grid item xs={12} md={3}>
                      <Card variant="outlined" sx={{ 
                        bgcolor: healthIndicators.performance_health === 'good' ? 'success.light' : 
                                healthIndicators.performance_health === 'warning' ? 'warning.light' : 'error.light',
                        color: healthIndicators.performance_health === 'good' ? 'success.contrastText' : 
                               healthIndicators.performance_health === 'warning' ? 'warning.contrastText' : 'error.contrastText'
                      }}>
                        <CardContent>
                          <Typography variant="h6" gutterBottom>
                            {healthIndicators.performance_health?.toUpperCase()}
                          </Typography>
                          <Typography variant="body2">
                            Performance Health
                          </Typography>
                        </CardContent>
                      </Card>
                    </Grid>
                    <Grid item xs={12} md={3}>
                      <Card variant="outlined" sx={{ 
                        bgcolor: healthIndicators.system_health === 'good' ? 'success.light' : 
                                healthIndicators.system_health === 'warning' ? 'warning.light' : 'error.light',
                        color: healthIndicators.system_health === 'good' ? 'success.contrastText' : 
                               healthIndicators.system_health === 'warning' ? 'warning.contrastText' : 'error.contrastText'
                      }}>
                        <CardContent>
                          <Typography variant="h6" gutterBottom>
                            {healthIndicators.system_health?.toUpperCase()}
                          </Typography>
                          <Typography variant="body2">
                            Overall System Health
                          </Typography>
                        </CardContent>
                      </Card>
                    </Grid>
                  </Grid>
                </Paper>
              )}

              {/* System Metrics */}
              {systemMetrics && (
                <Paper sx={{ p: 2, mb: 2 }}>
                  <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center' }}>
                    <SpeedIcon sx={{ mr: 1, color: 'primary.main' }} />
                    System Metrics
                  </Typography>
                  <Grid container spacing={2}>
                    <Grid item xs={12} md={4}>
                      <Typography variant="body2" color="text.secondary">
                        Error Rate Percentage
                      </Typography>
                      <Typography variant="h6">
                        {systemMetrics.error_rate_percentage ? `${systemMetrics.error_rate_percentage.toFixed(2)}%` : 'N/A'}
                      </Typography>
                    </Grid>
                    <Grid item xs={12} md={4}>
                      <Typography variant="body2" color="text.secondary">
                        Critical Errors Count
                      </Typography>
                      <Typography variant="h6">
                        {systemMetrics.critical_error_count || 0}
                      </Typography>
                    </Grid>
                    <Grid item xs={12} md={4}>
                      <Typography variant="body2" color="text.secondary">
                        Unique Error Categories
                      </Typography>
                      <Typography variant="h6">
                        {systemMetrics.unique_error_categories || 0}
                      </Typography>
                    </Grid>
                  </Grid>
                </Paper>
              )}

              {/* Performance Issues */}
              {performanceIssues && performanceIssues.length > 0 && (
                <Paper sx={{ p: 2, mb: 2 }}>
                  <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center' }}>
                    <WarningIcon sx={{ mr: 1, color: 'warning.main' }} />
                    Performance Issues
                  </Typography>
                  {performanceIssues.map((issue, index) => (
                    <Alert key={index} severity={issue.severity || 'warning'} sx={{ mb: 1 }}>
                      <AlertTitle>
                        {issue.type === 'high_memory' ? 'High Memory Usage' : 
                         issue.type === 'high_cpu' ? 'High CPU Usage' : issue.type}
                      </AlertTitle>
                      {issue.details}
                    </Alert>
                  ))}
                </Paper>
              )}
            </>
          )}
        </Box>

        {/* Error Analysis Tab */}
        <Box role="tabpanel" hidden={tabValue !== 3}>
          {loading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
              <CircularProgress />
            </Box>
          ) : (
            <>
              {/* Error Summary */}
              {errorAnalysis && (
                <Paper sx={{ p: 2, mb: 2 }}>
                  <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center' }}>
                    <ErrorIcon sx={{ mr: 1, color: 'error.main' }} />
                    Error Analysis Summary
                  </Typography>
                  <Grid container spacing={2}>
                    <Grid item xs={12} md={3}>
                      <Typography variant="body2" color="text.secondary">
                        Total Errors (24h)
                      </Typography>
                      <Typography variant="h6">
                        {errorAnalysis.total_errors || 0}
                      </Typography>
                    </Grid>
                    <Grid item xs={12} md={3}>
                      <Typography variant="body2" color="text.secondary">
                        Critical Errors
                      </Typography>
                      <Typography variant="h6" color="error.main">
                        {errorAnalysis.critical_errors || 0}
                      </Typography>
                    </Grid>
                    <Grid item xs={12} md={3}>
                      <Typography variant="body2" color="text.secondary">
                        Error Categories
                      </Typography>
                      <Typography variant="h6">
                        {errorAnalysis.error_categories ? Object.keys(errorAnalysis.error_categories).length : 0}
                      </Typography>
                    </Grid>
                    <Grid item xs={12} md={3}>
                      <Typography variant="body2" color="text.secondary">
                        Sessions with Errors
                      </Typography>
                      <Typography variant="h6">
                        {errorAnalysis.sessions_with_errors || 0}
                      </Typography>
                    </Grid>
                  </Grid>
                </Paper>
              )}

              {/* Error Categories Breakdown */}
              {errorAnalysis && errorAnalysis.error_categories && (
                <Paper sx={{ p: 2, mb: 2 }}>
                  <Typography variant="h6" gutterBottom>
                    Error Categories
                  </Typography>
                  <Grid container spacing={2}>
                    {Object.entries(errorAnalysis.error_categories).map(([category, count], index) => (
                      <Grid item xs={12} md={4} key={index}>
                        <Card variant="outlined" sx={{ bgcolor: 'error.light', color: 'error.contrastText' }}>
                          <CardContent>
                            <Typography variant="h6" gutterBottom>
                              {count}
                            </Typography>
                            <Typography variant="body2">
                              {category.charAt(0).toUpperCase() + category.slice(1)} Errors
                            </Typography>
                          </CardContent>
                        </Card>
                      </Grid>
                    ))}
                  </Grid>
                </Paper>
              )}

              {/* Error Timeline */}
              {errorTimeline && errorTimeline.length > 0 && (
                <Paper sx={{ p: 2, mb: 2 }}>
                  <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center' }}>
                    <TimelineIcon sx={{ mr: 1, color: 'primary.main' }} />
                    Recent Error Timeline
                  </Typography>
                  <List>
                    {errorTimeline.slice(0, 10).map((error, index) => (
                      <ListItem key={index} divider>
                        <ListItemIcon>
                          <Chip 
                            label={error.level || 'ERROR'} 
                            size="small" 
                            color={error.level === 'critical' ? 'error' : 'warning'}
                          />
                        </ListItemIcon>
                        <ListItemText
                          primary={error.message}
                          secondary={
                            <>
                              <Typography component="span" variant="body2" color="text.primary">
                                {formatDate(error.timestamp)}
                              </Typography>
                              {error.category && (
                                <Chip 
                                  label={error.category} 
                                  size="small" 
                                  variant="outlined" 
                                  sx={{ ml: 1 }}
                                />
                              )}
                              {error.session_id && (
                                <Chip 
                                  label={`Session: ${error.session_id.slice(0, 8)}`} 
                                  size="small" 
                                  variant="outlined" 
                                  sx={{ ml: 1 }}
                                />
                              )}
                            </>
                          }
                        />
                      </ListItem>
                    ))}
                  </List>
                </Paper>
              )}
            </>
          )}
        </Box>

        {/* Diagnostic Recommendations Tab */}
        <Box role="tabpanel" hidden={tabValue !== 4}>
          {loading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
              <CircularProgress />
            </Box>
          ) : (
            <>
              {/* Diagnostic Recommendations */}
              {diagnosticRecommendations && diagnosticRecommendations.length > 0 && (
                <Paper sx={{ p: 2, mb: 2 }}>
                  <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center' }}>
                    <BuildIcon sx={{ mr: 1, color: 'success.main' }} />
                    Diagnostic Recommendations
                  </Typography>
                  {diagnosticRecommendations.map((recommendation, index) => (
                    <Card key={index} sx={{ mb: 2, border: '1px solid', borderColor: 
                      recommendation.priority === 'critical' ? 'error.main' :
                      recommendation.priority === 'high' ? 'warning.main' : 'info.main'
                    }}>
                      <CardContent>
                        <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                          <Chip 
                            label={recommendation.priority?.toUpperCase() || 'MEDIUM'} 
                            size="small" 
                            color={
                              recommendation.priority === 'critical' ? 'error' :
                              recommendation.priority === 'high' ? 'warning' : 'info'
                            }
                          />
                          <Typography variant="h6" sx={{ ml: 2 }}>
                            {recommendation.issue || 'System Issue'}
                          </Typography>
                        </Box>
                        <Typography variant="body1" sx={{ mb: 2 }}>
                          {recommendation.recommendation}
                        </Typography>
                        {recommendation.actions && recommendation.actions.length > 0 && (
                          <>
                            <Typography variant="subtitle2" gutterBottom>
                              Recommended Actions:
                            </Typography>
                            <List dense>
                              {recommendation.actions.map((action, actionIndex) => (
                                <ListItem key={actionIndex}>
                                  <ListItemIcon>
                                    <CheckCircleIcon fontSize="small" />
                                  </ListItemIcon>
                                  <ListItemText primary={action} />
                                </ListItem>
                              ))}
                            </List>
                          </>
                        )}
                      </CardContent>
                    </Card>
                  ))}
                </Paper>
              )}

              {/* System Status Overview */}
              {comprehensiveStats && (
                <Paper sx={{ p: 2, mb: 2 }}>
                  <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center' }}>
                    <AssessmentIcon sx={{ mr: 1, color: 'primary.main' }} />
                    Comprehensive Statistics
                  </Typography>
                  <Grid container spacing={2}>
                    <Grid item xs={12} md={6}>
                      <Typography variant="subtitle2" gutterBottom>
                        Log Entries by Level
                      </Typography>
                      {comprehensiveStats.entries_by_level && Object.entries(comprehensiveStats.entries_by_level).map(([level, count]) => (
                        <Box key={level} sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                          <Typography variant="body2">{level.toUpperCase()}:</Typography>
                          <Typography variant="body2" fontWeight="bold">{count}</Typography>
                        </Box>
                      ))}
                    </Grid>
                    <Grid item xs={12} md={6}>
                      <Typography variant="subtitle2" gutterBottom>
                        Entries by Event Type
                      </Typography>
                      {comprehensiveStats.entries_by_type && Object.entries(comprehensiveStats.entries_by_type).map(([type, count]) => (
                        <Box key={type} sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                          <Typography variant="body2">{type}:</Typography>
                          <Typography variant="body2" fontWeight="bold">{count}</Typography>
                        </Box>
                      ))}
                    </Grid>
                  </Grid>
                </Paper>
              )}

              {/* No Data Message */}
              {(!diagnosticRecommendations || diagnosticRecommendations.length === 0) && 
               (!comprehensiveStats) && (
                <Paper sx={{ p: 4, textAlign: 'center' }}>
                  <InfoIcon sx={{ fontSize: 48, color: 'text.secondary', mb: 2 }} />
                  <Typography variant="h6" color="text.secondary">
                    Keine Diagnose-Informationen verfügbar
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Starten Sie den Scraper oder warten Sie auf Log-Daten für detaillierte Diagnose-Empfehlungen.
                  </Typography>
                </Paper>
              )}
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
