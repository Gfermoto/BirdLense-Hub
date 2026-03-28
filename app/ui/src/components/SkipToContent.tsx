import { useTranslation } from 'react-i18next';
import Button from '@mui/material/Button';

/**
 * First focusable control for keyboard users; moves focus to #main-content.
 */
export function SkipToContent() {
  const { t } = useTranslation();

  const handleClick = (e: React.MouseEvent<HTMLAnchorElement>) => {
    e.preventDefault();
    const el = document.getElementById('main-content');
    el?.focus({ preventScroll: false });
    el?.scrollIntoView({ block: 'start', behavior: 'smooth' });
  };

  return (
    <Button
      component="a"
      href="#main-content"
      onClick={handleClick}
      variant="contained"
      size="small"
      sx={{
        position: 'absolute',
        left: -9999,
        top: 0,
        zIndex: 2000,
        minWidth: 'auto',
        px: 2,
        py: 1,
        '&:focus-visible': {
          left: 16,
          top: 12,
        },
      }}
    >
      {t('common.skipToContent')}
    </Button>
  );
}
