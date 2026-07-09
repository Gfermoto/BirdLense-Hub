import type { TFunction } from 'i18next';
import type { HelpAudience } from '../hooks/useHelpAudience';
import type { HelpDetail } from '../components/PageHelp';

export interface PageHelpBundle {
  title: string;
  description?: string;
  details?: HelpDetail[];
}

function isPageHelpBundle(value: unknown): value is PageHelpBundle {
  return (
    typeof value === 'object' &&
    value !== null &&
    'title' in value &&
    typeof (value as PageHelpBundle).title === 'string'
  );
}

/** Role-scoped help: `help.<page>.<guest|operator|admin>`, then legacy `help.<page>`. */
export function resolvePageHelp(
  t: TFunction,
  configKey: string,
  audience: HelpAudience,
): PageHelpBundle {
  const roleKey = `help.${configKey}.${audience}`;
  const roleData = t(roleKey, { returnObjects: true });
  if (isPageHelpBundle(roleData)) {
    return {
      title: roleData.title,
      description: roleData.description,
      details: Array.isArray(roleData.details) ? roleData.details : undefined,
    };
  }

  const legacyKey = `help.${configKey}`;
  const legacy = t(legacyKey, { returnObjects: true });
  if (isPageHelpBundle(legacy)) {
    return {
      title: legacy.title,
      description: legacy.description,
      details: Array.isArray(legacy.details) ? legacy.details : undefined,
    };
  }

  return { title: '', description: '', details: [] };
}
