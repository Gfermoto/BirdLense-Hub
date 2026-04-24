import * as React from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { LanguageSwitcher } from './LanguageSwitcher';
import AppBar from '@mui/material/AppBar';
import logoUrl from '../assets/logo.png';
import Box from '@mui/material/Box';
import Container from '@mui/material/Container';
import Button from '@mui/material/Button';
import IconButton from '@mui/material/IconButton';
import Menu from '@mui/material/Menu';
import MenuItem from '@mui/material/MenuItem';
import Toolbar from '@mui/material/Toolbar';
import Typography from '@mui/material/Typography';
import MenuIcon from '@mui/icons-material/Menu';
import LogoutIcon from '@mui/icons-material/Logout';
import SettingsIcon from '@mui/icons-material/Settings';
import FiberManualRecordIcon from '@mui/icons-material/FiberManualRecord';
import FavoriteIcon from '@mui/icons-material/Favorite';
import Divider from '@mui/material/Divider';
import { keyframes } from '@emotion/react';
import { StatusIndicator } from './StatusIndicator';
import { useProtectedArea } from '../contexts/ProtectedAreaContext';
import { SettingsPasswordDialog } from './SettingsPasswordDialog';
import { useQuery } from '@tanstack/react-query';
import { fetchFeedInfo } from '../api/api';
import { queryKeys } from '../api/queryKeys';

// Pulse animation for the live indicator
const pulse = keyframes`
  0% {
    opacity: 1;
    transform: scale(1);
  }
  50% {
    opacity: 0.6;
    transform: scale(1.1);
  }
  100% {
    opacity: 1;
    transform: scale(1);
  }
`;

const heartbeat = keyframes`
  0%, 100% {
    transform: scale(1);
  }
  20% {
    transform: scale(1.2);
  }
  40% {
    transform: scale(1);
  }
  55% {
    transform: scale(1.12);
  }
  70% {
    transform: scale(1);
  }
`;

const NAV_KEYS = [
  { key: 'dashboard', path: '/' },
  { key: 'timeline', path: '/timeline' },
  { key: 'species', path: '/species' },
  { key: 'food', path: '/food' },
] as const;

// Pill-shaped nav item styles (defined outside component to avoid recreation)
const navPillStyles = {
  px: 2.5,
  py: 1,
  borderRadius: '20px',
  fontSize: '0.9rem',
  fontWeight: 500,
  color: 'rgba(255, 255, 255, 0.75)',
  textDecoration: 'none',
  border: '1px solid rgba(255, 255, 255, 0.08)',
  transition: 'all 0.2s',
  '&:hover': {
    bgcolor: 'rgba(255, 255, 255, 0.1)',
    color: 'white',
    borderColor: 'rgba(255, 255, 255, 0.18)',
  },
};

const activeNavPillStyles = {
  ...navPillStyles,
  bgcolor: 'rgba(255, 255, 255, 0.15)',
  color: 'white',
  fontWeight: 600,
  borderColor: 'rgba(255, 255, 255, 0.22)',
};

type PendingAction =
  | { type: 'openMenu' }
  | {
      type: 'navigate';
      path: string;
      minRole?: 'contributor' | 'admin';
    };

export function Navigation() {
  const { t } = useTranslation();
  const location = useLocation();
  const navigate = useNavigate();
  const currentPath = location.pathname.split('?')[0];
  const {
    requiresPassword,
    unlocked,
    setUnlocked,
    logoutAccess,
    isLoading,
    isAdmin,
  } = useProtectedArea();
  /** Настройки: только гость (вход) или админ. Оператор (contributor) — без пункта «Настройки». */
  const showSettingsLink = !requiresPassword || !unlocked || isAdmin;
  /** Система/библиотека: гость или админ (оператор после входа не видит). */
  const showAdminOnlyLinks = !requiresPassword || !unlocked || isAdmin;
  const gearButtonRef = React.useRef<HTMLButtonElement>(null);

  const [mobileMenuAnchor, setMobileMenuAnchor] =
    React.useState<null | HTMLElement>(null);
  const [settingsMenuAnchor, setSettingsMenuAnchor] =
    React.useState<null | HTMLElement>(null);
  const [showPasswordDialog, setShowPasswordDialog] = React.useState(false);
  const [pendingAction, setPendingAction] =
    React.useState<PendingAction | null>(null);

  const { data: feedInfo } = useQuery({
    queryKey: queryKeys.feed.info,
    queryFn: fetchFeedInfo,
    staleTime: 1000 * 30,
  });
  const donateUrl = feedInfo?.donate_url?.trim() || '';
  const showAppBarDonate = Boolean(donateUrl);

  const handleMobileMenuClose = () => setMobileMenuAnchor(null);
  const handleSettingsMenuClose = () => setSettingsMenuAnchor(null);

  const handlePasswordSuccess = (role?: 'admin' | 'contributor') => {
    setUnlocked(true, role || 'admin');
    setShowPasswordDialog(false);
    if (pendingAction) {
      if (pendingAction.type === 'openMenu' && gearButtonRef.current) {
        setSettingsMenuAnchor(gearButtonRef.current);
      } else if (pendingAction.type === 'navigate') {
        const grantedRole = role || 'admin';
        const canProceed =
          !pendingAction.minRole ||
          grantedRole === pendingAction.minRole ||
          grantedRole === 'admin';
        if (canProceed) {
          navigate(pendingAction.path);
          setMobileMenuAnchor(null);
        }
      }
      setPendingAction(null);
    }
  };

  const needsPassword = isLoading || (requiresPassword && !unlocked);
  const isReviewRoute =
    currentPath === '/timeline' &&
    /(?:^|[?&])review=1(?:&|$)/.test(location.search);

  const isNavItemActive = (path: string) =>
    currentPath === path && !(path === '/timeline' && isReviewRoute);

  const handleGearClick = (e: React.MouseEvent<HTMLButtonElement>) => {
    if (needsPassword) {
      setPendingAction({ type: 'openMenu' });
      setShowPasswordDialog(true);
    } else {
      setSettingsMenuAnchor(e.currentTarget);
    }
  };

  const handleProtectedNav = (
    path: string,
    e: React.MouseEvent,
    minRole?: 'contributor' | 'admin',
  ) => {
    e.preventDefault();
    if (needsPassword) {
      setPendingAction({ type: 'navigate', path, minRole });
      setShowPasswordDialog(true);
    } else {
      navigate(path);
      setMobileMenuAnchor(null);
    }
  };

  const handleLogout = async () => {
    handleSettingsMenuClose();
    handleMobileMenuClose();
    await logoutAccess();
    navigate('/');
  };

  const showLogout = requiresPassword && unlocked;

  return (
    <AppBar position="sticky" color="primary" sx={{ mb: 3 }}>
      <Container maxWidth="xl">
        <Toolbar disableGutters sx={{ gap: 1 }}>
          {/* Logo Section - Desktop (Clickable) */}
          <Box
            component={Link}
            to="/"
            sx={{
              display: { xs: 'none', md: 'flex' },
              alignItems: 'center',
              textDecoration: 'none',
              color: 'inherit',
              mr: 3,
              transition: 'opacity 0.2s ease-in-out',
              '&:hover': {
                opacity: 0.85,
              },
            }}
          >
            <Box
              component="img"
              src={logoUrl}
              alt="BirdLense Hub Logo"
              sx={{ mr: 1.5, height: 40, width: 40, borderRadius: 1 }}
            />
            <Typography variant="h6" sx={{ fontWeight: 700 }}>
              {t('common.appName')}
            </Typography>
          </Box>

          {/* Mobile: menu | logo | donate icon (только шапка, без пункта в drawer) */}
          <Box
            sx={{
              flexGrow: 1,
              display: { xs: 'flex', md: 'none' },
              alignItems: 'center',
              minWidth: 0,
              gap: 0.5,
            }}
          >
            <IconButton
              size="large"
              onClick={(e) => setMobileMenuAnchor(e.currentTarget)}
              color="inherit"
              aria-label={t('common.openMenu')}
            >
              <MenuIcon />
            </IconButton>
            <Menu
              anchorEl={mobileMenuAnchor}
              open={Boolean(mobileMenuAnchor)}
              onClose={handleMobileMenuClose}
              keepMounted
              anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
              transformOrigin={{ vertical: 'top', horizontal: 'left' }}
              slotProps={{
                paper: {
                  sx: {
                    borderRadius: 2,
                    mt: 1,
                  },
                },
              }}
            >
              {/* Main Navigation Items */}
              {NAV_KEYS.map((item) => (
                <MenuItem
                  key={item.path}
                  onClick={handleMobileMenuClose}
                  component={Link}
                  to={item.path}
                  selected={
                    currentPath === item.path &&
                    !(item.path === '/timeline' && isReviewRoute)
                  }
                >
                  {t(`nav.${item.key}`)}
                </MenuItem>
              ))}

              {/* Live View */}
              <MenuItem
                onClick={handleMobileMenuClose}
                component={Link}
                to="/live"
                selected={currentPath === '/live'}
                sx={{
                  color: '#fca5a5',
                  '&.Mui-selected': {
                    backgroundColor: 'rgba(185, 28, 28, 0.2)',
                  },
                }}
              >
                <FiberManualRecordIcon
                  sx={{
                    mr: 1,
                    fontSize: 14,
                    animation: `${pulse} 1.5s ease-in-out infinite`,
                  }}
                />
                {t('nav.liveView')}
              </MenuItem>

              {/* Settings Section — только гость (вход) или админ; оператор без доступа */}
              {showSettingsLink || showAdminOnlyLinks ? (
                <Divider key="mobile-menu-divider-admin" />
              ) : null}
              {showSettingsLink ? (
                <MenuItem
                  key="mobile-menu-settings"
                  onClick={(e) => handleProtectedNav('/settings', e, 'admin')}
                  selected={currentPath === '/settings'}
                  title={t('nav.settingsHint')}
                >
                  <SettingsIcon sx={{ mr: 1, fontSize: 20 }} />
                  {t('nav.settings')}
                </MenuItem>
              ) : null}
              {showAdminOnlyLinks ? (
                <MenuItem
                  key="mobile-menu-system"
                  onClick={(e) => handleProtectedNav('/system', e, 'admin')}
                  selected={currentPath === '/system'}
                  title={t('nav.systemHint')}
                >
                  {t('nav.system')}
                </MenuItem>
              ) : null}
              {showAdminOnlyLinks ? (
                <MenuItem
                  key="mobile-menu-library"
                  onClick={(e) => handleProtectedNav('/library', e, 'admin')}
                  selected={currentPath === '/library'}
                  title={t('nav.libraryHint')}
                >
                  {t('nav.library')}
                </MenuItem>
              ) : null}
              {showLogout ? <Divider key="mobile-menu-divider-logout" /> : null}
              {showLogout ? (
                <MenuItem
                  key="mobile-menu-logout"
                  onClick={() => void handleLogout()}
                >
                  <LogoutIcon sx={{ mr: 1, fontSize: 20 }} />
                  {t('nav.logout')}
                </MenuItem>
              ) : null}

              {/* Mobile: Status + Language */}
              <Divider />
              <Box
                sx={{
                  px: 2,
                  py: 1.5,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 2,
                  flexWrap: 'wrap',
                }}
              >
                <StatusIndicator />
                <LanguageSwitcher />
              </Box>
            </Menu>

            <Box
              component={Link}
              to="/"
              sx={{
                flex: 1,
                minWidth: 0,
                display: 'flex',
                alignItems: 'center',
                textDecoration: 'none',
                color: 'inherit',
                overflow: 'hidden',
              }}
            >
              <Box
                component="img"
                src={logoUrl}
                alt="BirdLense Hub Logo"
                sx={{
                  mr: 1,
                  height: 32,
                  width: 32,
                  borderRadius: 0.5,
                  flexShrink: 0,
                }}
              />
              <Typography variant="h6" noWrap>
                {t('common.appName')}
              </Typography>
            </Box>

            {showAppBarDonate ? (
              <IconButton
                component="a"
                href={donateUrl}
                target="_blank"
                rel="noopener noreferrer"
                size="small"
                color="inherit"
                aria-label={t('nav.supportProject')}
                sx={{
                  flexShrink: 0,
                  color: 'rgba(255, 255, 255, 0.92)',
                }}
              >
                <FavoriteIcon
                  sx={{
                    fontSize: 22,
                    color: '#fca5a5',
                    animation: `${heartbeat} 1.25s ease-in-out infinite`,
                  }}
                />
              </IconButton>
            ) : null}
          </Box>

          {/* Desktop Navigation - Pill Style */}
          <Box
            sx={{
              flexGrow: 1,
              display: { xs: 'none', md: 'flex' },
              gap: 0.9,
              alignItems: 'center',
            }}
          >
            {NAV_KEYS.map((item) => (
              <Box
                key={item.path}
                component={Link}
                to={item.path}
                aria-current={isNavItemActive(item.path) ? 'page' : undefined}
                sx={isNavItemActive(item.path) ? activeNavPillStyles : navPillStyles}
              >
                {t(`nav.${item.key}`)}
              </Box>
            ))}
          </Box>

          {/* Action Buttons - Desktop */}
          <Box
            sx={{
              display: { xs: 'none', md: 'flex' },
              gap: 1.5,
              alignItems: 'center',
            }}
          >
            {/* Live Button - Red with pulse */}
            <Button
              component={Link}
              to="/live"
              aria-current={currentPath === '/live' ? 'page' : undefined}
              startIcon={
                <FiberManualRecordIcon
                  sx={{
                    fontSize: 12,
                    animation: `${pulse} 1.5s ease-in-out infinite`,
                  }}
                />
              }
              sx={{
                /* red-700 / red-800: WCAG AA vs white text (≥4.5:1) */
                bgcolor: currentPath === '/live' ? '#991b1b' : '#b91c1c',
                color: '#ffffff',
                px: 2.5,
                py: 0.75,
                borderRadius: '20px',
                fontWeight: 600,
                textTransform: 'none',
                boxShadow:
                  currentPath === '/live'
                    ? '0 0 20px rgba(185, 28, 28, 0.45)'
                    : '0 0 12px rgba(185, 28, 28, 0.35)',
                transition: 'all 0.2s ease-in-out',
                '&:hover': {
                  bgcolor: '#991b1b',
                  boxShadow: '0 0 24px rgba(153, 27, 27, 0.55)',
                  transform: 'translateY(-1px)',
                },
              }}
            >
              {t('nav.liveView')}
            </Button>

            {/* Component Status */}
            <Box sx={{ display: { xs: 'none', sm: 'flex' } }}>
              <StatusIndicator />
            </Box>

            {/* Language Switcher */}
            <LanguageSwitcher />

            {showAppBarDonate ? (
              <IconButton
                component="a"
                href={donateUrl}
                target="_blank"
                rel="noopener noreferrer"
                size="small"
                color="inherit"
                aria-label={t('nav.supportProject')}
                title={t('nav.supportProject')}
                sx={{
                  color: 'rgba(255, 255, 255, 0.92)',
                  '&:hover': { bgcolor: 'rgba(255, 255, 255, 0.12)' },
                }}
              >
                <FavoriteIcon
                  sx={{
                    fontSize: 22,
                    color: '#fca5a5',
                    animation: `${heartbeat} 1.25s ease-in-out infinite`,
                  }}
                />
              </IconButton>
            ) : null}

            {/* Settings Icon */}
            <IconButton
              ref={gearButtonRef}
              color="inherit"
              onClick={handleGearClick}
              aria-label={t('common.openSettingsMenu')}
              aria-controls="settings-menu"
              aria-expanded={Boolean(settingsMenuAnchor)}
              sx={{
                '&:hover': {
                  bgcolor: 'rgba(255, 255, 255, 0.1)',
                },
              }}
            >
              <SettingsIcon />
            </IconButton>
          </Box>

          {/* Settings Menu - Desktop */}
          <Menu
            id="settings-menu"
            anchorEl={settingsMenuAnchor}
            open={Boolean(settingsMenuAnchor)}
            onClose={handleSettingsMenuClose}
            anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
            transformOrigin={{ vertical: 'top', horizontal: 'right' }}
            slotProps={{
              paper: {
                sx: {
                  borderRadius: 2,
                  mt: 1,
                  minWidth: 160,
                },
              },
            }}
          >
            {showSettingsLink ? (
              <MenuItem
                key="settings-menu-station"
                component={Link}
                to="/settings"
                onClick={handleSettingsMenuClose}
                selected={currentPath === '/settings'}
                title={t('nav.settingsHint')}
              >
                {t('nav.settings')}
              </MenuItem>
            ) : null}
            {showAdminOnlyLinks ? (
              <MenuItem
                key="settings-menu-system"
                component={Link}
                to="/system"
                onClick={handleSettingsMenuClose}
                selected={currentPath === '/system'}
                title={t('nav.systemHint')}
              >
                {t('nav.system')}
              </MenuItem>
            ) : null}
            {showAdminOnlyLinks ? (
              <MenuItem
                key="settings-menu-library"
                component={Link}
                to="/library"
                onClick={handleSettingsMenuClose}
                selected={currentPath === '/library'}
                title={t('nav.libraryHint')}
              >
                {t('nav.library')}
              </MenuItem>
            ) : null}
            {showLogout ? <Divider key="settings-menu-divider-logout" /> : null}
            {showLogout ? (
              <MenuItem
                key="settings-menu-logout"
                onClick={() => void handleLogout()}
                sx={{ color: 'error.main' }}
              >
                <LogoutIcon sx={{ mr: 1, fontSize: 20 }} />
                {t('nav.logout')}
              </MenuItem>
            ) : null}
          </Menu>
        </Toolbar>
      </Container>
      <SettingsPasswordDialog
        open={showPasswordDialog}
        onSuccess={handlePasswordSuccess}
        onClose={() => {
          setShowPasswordDialog(false);
          setPendingAction(null);
        }}
      />
    </AppBar>
  );
}
