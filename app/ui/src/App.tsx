import { Suspense, lazy, useEffect, useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import Container from '@mui/material/Container';
import Box from '@mui/material/Box';
import CircularProgress from '@mui/material/CircularProgress';
import CssBaseline from '@mui/material/CssBaseline';
import Typography from '@mui/material/Typography';
import { i18n } from './i18n';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import { ProtectedAreaProvider } from './contexts/ProtectedAreaContext';
import { Navigation } from './components/Navigation';
import { SkipToContent } from './components/SkipToContent';
import { Footer } from './components/Footer';
import { InstallPrompt } from './components/InstallPrompt';
import { PwaUpdatePrompt } from './components/PwaUpdatePrompt';
import { ErrorBoundary } from './components/ErrorBoundary';
import { trackSiteVisitor } from './api/systemAuditMetrics';

const Overview = lazy(() => import('./pages/Overview'));
const TimelinePage = lazy(() => import('./pages/Timeline'));
const FavoritesPage = lazy(() => import('./pages/Favorites'));
const VideoDetails = lazy(() =>
  import('./pages/VideoDetails').then((m) => ({ default: m.VideoDetails })),
);
const FoodManagement = lazy(() =>
  import('./pages/FoodManagement').then((m) => ({ default: m.FoodManagement })),
);
const LivePage = lazy(() =>
  import('./pages/Live').then((m) => ({ default: m.LivePage })),
);
const Settings = lazy(() =>
  import('./pages/Settings').then((m) => ({ default: m.Settings })),
);
const SpeciesDirectoryPage = lazy(() => import('./pages/SpeciesDirectory'));
const SpeciesSummary = lazy(() => import('./pages/SpeciesSummary'));
const System = lazy(() =>
  import('./pages/System').then((m) => ({ default: m.System })),
);
const Library = lazy(() =>
  import('./pages/Library').then((m) => ({ default: m.Library })),
);
const LabellingPage = lazy(() => import('./pages/Labelling'));
const MigrationCalendar = lazy(() =>
  import('./pages/MigrationCalendar').then((m) => ({
    default: m.MigrationCalendar,
  })),
);
const NotFoundPage = lazy(() => import('./pages/NotFound'));

/** Keyboard focus ring (WCAG 2.4.7); distinct from mouse-only :focus where supported. */
const focusVisibleOutline = {
  outline: '2px solid #5EEAD4',
  outlineOffset: '2px',
} as const;

const theme = createTheme({
  palette: {
    mode: 'dark',
    background: {
      default: '#0F172A', // Slate 900
      paper: '#1E293B', // Slate 800
    },
    primary: {
      main: '#10B981', // Emerald 500 (readable on dark background as text/outline color)
      /** Текст/иконки на сплошной заливке primary — WCAG AA для обычного текста */
      dark: '#047857',
      light: '#34D399',
      contrastText: '#ffffff',
    },
    secondary: {
      main: '#0EA5E9', // Sky 500
      contrastText: '#ffffff',
    },
    text: {
      primary: '#F8FAFC', // Slate 50
      secondary: '#CBD5E1', // Slate 300; readable on dark cards/forms
    },
  },
  shape: {
    borderRadius: 12,
  },
  typography: {
    fontFamily: '"Inter", "Roboto", "Helvetica", "Arial", sans-serif',
    h1: { fontWeight: 700 },
    h2: { fontWeight: 700 },
    h3: { fontWeight: 600 },
    h4: { fontWeight: 600 },
    h5: { fontWeight: 600 },
    h6: { fontWeight: 600 },
    button: { textTransform: 'none', fontWeight: 600 },
  },
  components: {
    MuiButtonBase: {
      styleOverrides: {
        root: {
          '&:focus-visible': focusVisibleOutline,
        },
      },
    },
    MuiCssBaseline: {
      styleOverrides: {
        body: {
          /** :any-link = link + visited одним цветом; не трогаем :visited отдельно — иначе перебиваем sx (футер и т.д.). */
          '& a:not(.MuiButtonBase-root):any-link': {
            color: '#5EEAD4',
            textDecorationColor: 'rgba(94, 234, 212, 0.45)',
          },
          '& a:not(.MuiButtonBase-root):hover': {
            color: '#99F6E4',
            textDecorationColor: 'rgba(153, 246, 228, 0.65)',
          },
          scrollbarColor: '#334155 #0F172A',
          '&::-webkit-scrollbar, & *::-webkit-scrollbar': {
            backgroundColor: '#0F172A',
            width: '8px',
          },
          '&::-webkit-scrollbar-thumb, & *::-webkit-scrollbar-thumb': {
            borderRadius: 8,
            backgroundColor: '#334155',
            minHeight: 24,
            border: '2px solid #0F172A',
          },
          '&::-webkit-scrollbar-thumb:focus, & *::-webkit-scrollbar-thumb:focus':
            {
              backgroundColor: '#475569',
            },
        },
        'a:focus-visible:not(.MuiButtonBase-root)': focusVisibleOutline,
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          backgroundImage: 'none',
          border: '1px solid rgba(148, 163, 184, 0.1)',
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: 'none',
        },
      },
    },
    MuiAppBar: {
      styleOverrides: {
        root: {
          backgroundColor: 'rgba(15, 23, 42, 0.8)',
          backdropFilter: 'blur(12px)',
          borderBottom: '1px solid rgba(148, 163, 184, 0.1)',
          backgroundImage: 'none',
          boxShadow: 'none',
        },
      },
    },
    /** White on primary.main (#10B981) fails WCAG AA for small text; emerald 700 is ≥4.5:1 vs white. */
    MuiChip: {
      styleOverrides: {
        filledPrimary: {
          backgroundColor: '#047857',
          color: '#ffffff',
          '&:hover': { backgroundColor: '#065f46' },
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        /** Keep contained primary buttons WCAG AA with white text. */
        containedPrimary: {
          '--variant-containedBg': '#047857',
          '--variant-containedHoverBg': '#065f46',
          backgroundColor: '#047857',
          color: '#ffffff',
          '&:hover': {
            backgroundColor: '#065f46',
          },
        },
      },
    },
    MuiFormHelperText: {
      styleOverrides: {
        root: {
          color: '#CBD5E1',
        },
      },
    },
    /** Avoid a11y tools flagging switches/checkboxes as read-only when they are editable. */
    MuiSwitch: {
      defaultProps: {
        slotProps: {
          input: { readOnly: false },
        },
      },
    },
    MuiCheckbox: {
      defaultProps: {
        slotProps: {
          input: { readOnly: false },
        },
      },
    },
    MuiInputLabel: {
      styleOverrides: {
        root: {
          color: '#CBD5E1',
          '&.Mui-focused': {
            color: '#5EEAD4',
          },
        },
      },
    },
    MuiOutlinedInput: {
      styleOverrides: {
        notchedOutline: {
          borderColor: 'rgba(203, 213, 225, 0.35)',
        },
        root: {
          '&:hover .MuiOutlinedInput-notchedOutline': {
            borderColor: 'rgba(203, 213, 225, 0.65)',
          },
          '&.Mui-focused .MuiOutlinedInput-notchedOutline': {
            borderColor: '#5EEAD4',
          },
        },
      },
    },
    MuiAlert: {
      styleOverrides: {
        root: {
          '& .MuiAlert-message': {
            color: '#F8FAFC',
          },
          '& .MuiAlert-icon': {
            color: 'inherit',
          },
        },
        standardInfo: {
          backgroundColor: 'rgba(14, 165, 233, 0.16)',
          color: '#E0F2FE',
          '& .MuiAlert-message .MuiButton-root': {
            color: '#7dd3fc',
          },
          '& .MuiAlert-message a:any-link': {
            color: '#7dd3fc',
          },
        },
        standardWarning: {
          backgroundColor: 'rgba(245, 158, 11, 0.18)',
          color: '#FEF3C7',
        },
        standardError: {
          backgroundColor: 'rgba(239, 68, 68, 0.18)',
          color: '#FEE2E2',
        },
        standardSuccess: {
          backgroundColor: 'rgba(16, 185, 129, 0.16)',
          color: '#D1FAE5',
        },
      },
    },
  },
});

function App() {
  useEffect(() => {
    try {
      if (typeof localStorage === 'undefined') {
        return;
      }
      const browserIdKey = 'birdlense.browser_id';
      const trackedDayKey = 'birdlense.visitor_tracked_day';
      const utcDay = new Date().toISOString().slice(0, 10);

      let browserId = localStorage.getItem(browserIdKey);
      if (!browserId) {
        browserId = globalThis.crypto?.randomUUID?.();
        if (!browserId) {
          return;
        }
        localStorage.setItem(browserIdKey, browserId);
      }
      if (localStorage.getItem(trackedDayKey) === utcDay) {
        return;
      }
      localStorage.setItem(trackedDayKey, utcDay);
      void trackSiteVisitor(browserId).catch(() => {
        localStorage.removeItem(trackedDayKey);
      });
    } catch {
      // Ignore tracking in restricted/private environments.
    }
  }, []);

  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 1000 * 60 * 5, // 5 minutes
            gcTime: 1000 * 60 * 15,
            refetchOnWindowFocus: false,
            retry: 1,
          },
        },
      }),
  );

  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <BrowserRouter
          future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
        >
          <ProtectedAreaProvider>
            <Box
              sx={{
                display: 'flex',
                flexDirection: 'column',
                minHeight: '100vh',
                position: 'relative',
              }}
            >
              <SkipToContent />
              <Navigation />
              <Box
                id="main-content"
                component="main"
                tabIndex={-1}
                sx={{ flexGrow: 1, pb: 4, outline: 'none' }}
              >
                <Container maxWidth="xl" sx={{ minWidth: 0 }}>
                  <Suspense
                    fallback={
                      <Box
                        role="status"
                        aria-live="polite"
                        aria-busy="true"
                        sx={{
                          display: 'flex',
                          flexDirection: 'column',
                          alignItems: 'center',
                          justifyContent: 'center',
                          gap: 2,
                          py: 8,
                        }}
                      >
                        <Typography
                          component="h1"
                          variant="h6"
                          sx={{
                            border: 0,
                            clip: 'rect(0 0 0 0)',
                            height: 1,
                            margin: -1,
                            overflow: 'hidden',
                            padding: 0,
                            position: 'absolute',
                            whiteSpace: 'nowrap',
                            width: 1,
                          }}
                        >
                          {i18n.t('common.pageLoading')}
                        </Typography>
                        <CircularProgress
                          aria-label={i18n.t('common.loading')}
                          size={44}
                        />
                        <Typography variant="body2" color="text.secondary">
                          {i18n.t('common.pageLoading')}
                        </Typography>
                      </Box>
                    }
                  >
                    <ErrorBoundary>
                      <Routes>
                        <Route path="/" element={<Overview />} />
                        <Route path="/timeline" element={<TimelinePage />} />
                        <Route path="/favorites" element={<FavoritesPage />} />
                        <Route
                          path="/migration-calendar"
                          element={<MigrationCalendar />}
                        />
                        <Route path="/videos/:id" element={<VideoDetails />} />
                        <Route path="/food" element={<FoodManagement />} />
                        <Route
                          path="/species"
                          element={<MigrationCalendar />}
                        />
                        <Route
                          path="/species-directory"
                          element={<SpeciesDirectoryPage />}
                        />
                        <Route path="/live" element={<LivePage />} />
                        <Route path="/settings" element={<Settings />} />
                        <Route
                          path="/species/:id"
                          element={<SpeciesSummary />}
                        />
                        <Route
                          path="/unknowns"
                          element={<Navigate to="/timeline?review=1" replace />}
                        />
                        <Route path="/system" element={<System />} />
                        <Route path="/library" element={<Library />} />
                        <Route path="/labelling" element={<LabellingPage />} />
                        <Route
                          path="/review"
                          element={<Navigate to="/timeline?review=1&queue=expert" replace />}
                        />
                        <Route path="*" element={<NotFoundPage />} />
                      </Routes>
                    </ErrorBoundary>
                  </Suspense>
                </Container>
              </Box>
              <Footer />
              <InstallPrompt />
              <PwaUpdatePrompt />
            </Box>
          </ProtectedAreaProvider>
        </BrowserRouter>
        {import.meta.env.DEV ? (
          <ReactQueryDevtools initialIsOpen={false} />
        ) : null}
      </ThemeProvider>
    </QueryClientProvider>
  );
}

export default App;
