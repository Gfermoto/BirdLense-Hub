import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';

export function useDocumentTitle(pageTitle?: string | null) {
  const { t } = useTranslation();

  useEffect(() => {
    if (typeof document === 'undefined') {
      return;
    }
    const appName = t('common.appName');
    document.title = pageTitle ? `${pageTitle} · ${appName}` : appName;
  }, [pageTitle, t]);
}
