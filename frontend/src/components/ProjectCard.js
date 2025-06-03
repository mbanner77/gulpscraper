import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Card,
  CardContent,
  CardActions,
  Typography,
  Button,
  Chip,
  Box,
  IconButton,
  Tooltip,
  CardMedia,
  Badge
} from '@mui/material';
import {
  Favorite as FavoriteIcon,
  FavoriteBorder as FavoriteBorderIcon,
  LocationOn as LocationIcon,
  CalendarToday as CalendarIcon,
  AccessTime as AccessTimeIcon,
  Laptop as LaptopIcon,
  FiberNew as NewIcon
} from '@mui/icons-material';
import { favoritesManager } from '../services/api';

function ProjectCard({ project, onFavoriteToggle, isNew = false, onMarkAsSeen = null }) {
  const navigate = useNavigate();
  const [isFavorite, setIsFavorite] = React.useState(
    favoritesManager.isFavorite(project.id)
  );
  
  // Format date to German locale
  const formatDate = (dateString) => {
    if (!dateString) return 'Nicht angegeben';
    const date = new Date(dateString);
    return date.toLocaleDateString('de-DE', {
      year: 'numeric',
      month: 'long',
      day: 'numeric'
    });
  };
  
  // Truncate description to a certain length
  const truncateDescription = (text, maxLength = 150) => {
    if (!text) return 'Keine Beschreibung vorhanden';
    return text.length > maxLength
      ? `${text.substring(0, maxLength)}...`
      : text;
  };
  
  const handleFavoriteClick = () => {
    if (isFavorite) {
      favoritesManager.removeFavorite(project.id);
    } else {
      favoritesManager.addFavorite(project);
    }
    setIsFavorite(!isFavorite);
    if (onFavoriteToggle) {
      onFavoriteToggle(project.id, !isFavorite);
    }
  };
  
  const handleCardClick = () => {
    navigate(`/project/${project.id}`);
  };

  // Wenn die Karte angeklickt wird und es ein neues Projekt ist, markieren wir es als gesehen
  const handleClick = () => {
    if (isNew && onMarkAsSeen) {
      onMarkAsSeen(project.id);
    }
  };

  return (
    <Card 
      sx={{ 
        height: '100%', 
        display: 'flex', 
        flexDirection: 'column',
        transition: 'transform 0.2s, box-shadow 0.2s',
        '&:hover': {
          transform: 'translateY(-4px)',
          boxShadow: '0 8px 16px rgba(0,0,0,0.1)',
        },
        ...(isNew && {
          border: '2px solid',
          borderColor: 'success.main',
          boxShadow: '0 0 10px rgba(76, 175, 80, 0.5)'
        })
      }}
      onClick={handleClick}
    >
      {project.companyLogoUrl && (
        <CardMedia
          component="img"
          height="60"
          image={project.companyLogoUrl}
          alt={project.companyName || 'Firmenlogo'}
          sx={{ 
            objectFit: 'contain', 
            backgroundColor: '#f5f5f5', 
            p: 1 
          }}
        />
      )}
      
      <CardContent sx={{ flexGrow: 1, position: 'relative' }}>
        {isNew && (
          <Tooltip title="Neues Projekt">
            <Chip
              icon={<NewIcon />}
              label="Neu"
              color="success"
              size="small"
              sx={{
                position: 'absolute',
                top: 8,
                right: 8,
                zIndex: 1
              }}
            />
          </Tooltip>
        )}
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <Typography 
            variant="h6" 
            component="h2" 
            gutterBottom
            sx={{ 
              fontWeight: 'bold',
              cursor: 'pointer',
              '&:hover': { color: 'primary.main' }
            }}
            onClick={handleCardClick}
          >
            {project.title}
          </Typography>
          <Tooltip title={isFavorite ? "Von Favoriten entfernen" : "Zu Favoriten hinzufügen"}>
            <IconButton 
              color={isFavorite ? "secondary" : "default"} 
              onClick={(e) => {
                e.stopPropagation();
                handleFavoriteClick();
              }}
              size="small"
            >
              {isFavorite ? <FavoriteIcon /> : <FavoriteBorderIcon />}
            </IconButton>
          </Tooltip>
        </Box>
        
        <Typography variant="body2" color="text.secondary" gutterBottom>
          {project.companyName || 'Unbekanntes Unternehmen'}
        </Typography>
        
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 1, flexWrap: 'wrap', gap: 0.5 }}>
          {project.location && (
            <Chip 
              icon={<LocationIcon fontSize="small" />} 
              label={project.location} 
              size="small" 
              variant="outlined"
            />
          )}
          
          {project.isRemoteWorkPossible && (
            <Chip 
              icon={<LaptopIcon fontSize="small" />} 
              label="Remote möglich" 
              size="small" 
              color="primary" 
              variant="outlined"
            />
          )}
        </Box>
        
        <Typography variant="body2" paragraph>
          {truncateDescription(project.description)}
        </Typography>
        
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mt: 'auto' }}>
          {project.originalPublicationDate && (
            <Box sx={{ display: 'flex', alignItems: 'center', mr: 2 }}>
              <CalendarIcon fontSize="small" sx={{ mr: 0.5, color: 'text.secondary' }} />
              <Typography variant="caption" color="text.secondary">
                Veröffentlicht: {formatDate(project.originalPublicationDate)}
              </Typography>
            </Box>
          )}
          
          {project.startDate && (
            <Box sx={{ display: 'flex', alignItems: 'center' }}>
              <AccessTimeIcon fontSize="small" sx={{ mr: 0.5, color: 'text.secondary' }} />
              <Typography variant="caption" color="text.secondary">
                Start: {project.startDate}
              </Typography>
            </Box>
          )}
        </Box>
      </CardContent>
      
      <CardActions>
        <Button 
          size="small" 
          color="primary" 
          onClick={handleCardClick}
        >
          Details ansehen
        </Button>
        
        {project.url && (
          <Button 
            size="small" 
            color="secondary"
            href={project.url}
            target="_blank"
            rel="noopener noreferrer"
          >
            Auf GULP ansehen
          </Button>
        )}
      </CardActions>
    </Card>
  );
}

export default ProjectCard;
