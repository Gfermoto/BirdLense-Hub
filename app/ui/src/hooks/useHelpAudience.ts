import { useProtectedArea } from '../contexts/ProtectedAreaContext';

/** Help copy tier for PageHelp and in-page guides. */
export type HelpAudience = 'guest' | 'operator' | 'admin';

export function useHelpAudience(): HelpAudience {
  const { canEdit, isAdmin } = useProtectedArea();
  if (!canEdit) {
    return 'guest';
  }
  if (isAdmin) {
    return 'admin';
  }
  return 'operator';
}
