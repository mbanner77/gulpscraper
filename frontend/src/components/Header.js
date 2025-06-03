import React, { useState } from 'react';
import { Link as RouterLink, useNavigate } from 'react-router-dom';
import {
  AppBar,
  Toolbar,
  Typography,
  Button,
  IconButton,
  Box,
  InputBase,
  Badge,
  Menu,
  MenuItem,
  useMediaQuery,
  useTheme,
  Drawer,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Divider
} from '@mui/material';
import {
  Search as SearchIcon,
  Favorite as FavoriteIcon,
  Menu as MenuIcon,
  Home as HomeIcon,
  Info as InfoIcon,
  Close as CloseIcon,
  DataUsage as DataUsageIcon,
  Settings as SettingsIcon,
  Notifications as NotificationsIcon
} from '@mui/icons-material';
import { styled, alpha } from '@mui/material/styles';

const navItems = [
  { text: 'Home', path: '/', icon: <HomeIcon /> },
  { text: 'Favorites', path: '/favorites', icon: <FavoriteIcon /> },
  { text: 'Projekte', path: '/scraper', icon: <DataUsageIcon /> },
  { text: 'Scraper-Verwaltung', path: '/scraper-control', icon: <SettingsIcon /> },
];

// Styled search component
const Search = styled('div')(({ theme }) => ({
  position: 'relative',
  borderRadius: theme.shape.borderRadius,
  backgroundColor: alpha(theme.palette.common.white, 0.15),
  '&:hover': {
    backgroundColor: alpha(theme.palette.common.white, 0.25),
  },
  marginRight: theme.spacing(2),
  marginLeft: 0,
  width: '100%',
  [theme.breakpoints.up('sm')]: {
    marginLeft: theme.spacing(3),
    width: 'auto',
  },
}));

const SearchIconWrapper = styled('div')(({ theme }) => ({
  padding: theme.spacing(0, 2),
  height: '100%',
  position: 'absolute',
  pointerEvents: 'none',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
}));

const StyledInputBase = styled(InputBase)(({ theme }) => ({
  color: 'inherit',
  '& .MuiInputBase-input': {
    padding: theme.spacing(1, 1, 1, 0),
    paddingLeft: `calc(1em + ${theme.spacing(4)})`,
    transition: theme.transitions.create('width'),
    width: '100%',
    [theme.breakpoints.up('md')]: {
      width: '20ch',
    },
  },
}));

function Header() {
  const theme = useTheme();
  const navigate = useNavigate();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const [mobileOpen, setMobileOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  
  // Get favorite count from localStorage
  const getFavoriteCount = () => {
    try {
      const favorites = JSON.parse(localStorage.getItem('favorites')) || [];
      return favorites.length;
    } catch (error) {
      console.error('Error getting favorites:', error);
      return 0;
    }
  };
  
  const handleSearchSubmit = (e) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      navigate(`/?search=${encodeURIComponent(searchQuery.trim())}`);
      setSearchQuery('');
      setMobileOpen(false);
    }
  };
  
  const handleDrawerToggle = () => {
    setMobileOpen(!mobileOpen);
  };
  
  const drawer = (
    <Box sx={{ width: 250 }} role="presentation">
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', p: 2 }}>
        <Typography variant="h6" component="div">
          GULP Job Viewer
        </Typography>
        <IconButton onClick={handleDrawerToggle}>
          <CloseIcon />
        </IconButton>
      </Box>
      <Divider />
      <List>
        <ListItem button component={RouterLink} to="/" onClick={handleDrawerToggle}>
          <ListItemIcon>
            <HomeIcon />
          </ListItemIcon>
          <ListItemText primary="Startseite" />
        </ListItem>
        <ListItem button component={RouterLink} to="/favorites" onClick={handleDrawerToggle}>
          <ListItemIcon>
            <FavoriteIcon />
          </ListItemIcon>
          <ListItemText primary="Favoriten" />
        </ListItem>
        <ListItem button component={RouterLink} to="/scraper" onClick={handleDrawerToggle}>
          <ListItemIcon>
            <DataUsageIcon />
          </ListItemIcon>
          <ListItemText primary="Projekte" />
        </ListItem>
        <ListItem button component={RouterLink} to="/scraper-control" onClick={handleDrawerToggle}>
          <ListItemIcon>
            <SettingsIcon />
          </ListItemIcon>
          <ListItemText primary="Scraper-Verwaltung" />
        </ListItem>
      </List>
      <Divider />
      <Box sx={{ p: 2 }}>
        <form onSubmit={handleSearchSubmit}>
          <Search>
            <SearchIconWrapper>
              <SearchIcon />
            </SearchIconWrapper>
            <StyledInputBase
              placeholder="Projekte suchen..."
              inputProps={{ 'aria-label': 'search' }}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              fullWidth
            />
          </Search>
        </form>
      </Box>
    </Box>
  );

  return (
    <>
      <AppBar position="sticky">
        <Toolbar>
          {isMobile && (
            <IconButton
              color="inherit"
              aria-label="open drawer"
              edge="start"
              onClick={handleDrawerToggle}
              sx={{ mr: 2 }}
            >
              <MenuIcon />
            </IconButton>
          )}
          
          <Typography
            variant="h6"
            component={RouterLink}
            to="/"
            sx={{
              display: { xs: 'none', sm: 'block' },
              textDecoration: 'none',
              color: 'inherit',
              flexGrow: 0
            }}
          >
            GULP Job Viewer
          </Typography>
          
          {!isMobile && (
            <form onSubmit={handleSearchSubmit} style={{ flexGrow: 1, display: 'flex' }}>
              <Search>
                <SearchIconWrapper>
                  <SearchIcon />
                </SearchIconWrapper>
                <StyledInputBase
                  placeholder="Projekte suchen..."
                  inputProps={{ 'aria-label': 'search' }}
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              </Search>
            </form>
          )}
          
          <Box sx={{ flexGrow: 1 }} />
          
          {!isMobile && (
            <Box sx={{ display: 'flex' }}>
              <Button color="inherit" component={RouterLink} to="/">
                Startseite
              </Button>
              <Button 
                color="inherit" 
                component={RouterLink} 
                to="/favorites"
                startIcon={
                  <Badge badgeContent={getFavoriteCount()} color="secondary">
                    <FavoriteIcon />
                  </Badge>
                }
              >
                Favoriten
              </Button>
              <Button color="inherit" component={RouterLink} to="/scraper">
                Projekte
              </Button>
              <Button color="inherit" component={RouterLink} to="/scraper-control">
                Scraper-Verwaltung
              </Button>
            </Box>
          )}
          
          {isMobile && (
            <IconButton 
              color="inherit" 
              component={RouterLink} 
              to="/favorites"
              aria-label="favorites"
            >
              <Badge badgeContent={getFavoriteCount()} color="secondary">
                <FavoriteIcon />
              </Badge>
            </IconButton>
          )}
        </Toolbar>
      </AppBar>
      
      <Drawer
        variant="temporary"
        open={mobileOpen}
        onClose={handleDrawerToggle}
        ModalProps={{
          keepMounted: true, // Better open performance on mobile
        }}
        sx={{
          display: { xs: 'block', md: 'none' },
          '& .MuiDrawer-paper': { boxSizing: 'border-box', width: 250 },
        }}
      >
        {drawer}
      </Drawer>
    </>
  );
}

export default Header;
