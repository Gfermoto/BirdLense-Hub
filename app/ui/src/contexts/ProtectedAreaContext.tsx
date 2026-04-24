import React, {
  createContext,
  useContext,
  useCallback,
  useState,
  useMemo,
} from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  checkSettingsAccess,
  fetchSettingsRequiresPassword,
  logoutSettingsSession,
} from '../api/settingsSession';
import { queryKeys } from '../api/queryKeys';

interface ProtectedAreaContextValue {
  requiresPassword: boolean;
  hasContributorTier: boolean;
  unlocked: boolean;
  role: 'admin' | 'contributor' | null;
  setUnlocked: (value: boolean, role?: 'admin' | 'contributor') => void;
  /** Сброс серверной сессии и локального состояния (смена оператор/админ за одним ПК). */
  logoutAccess: () => Promise<void>;
  isLoading: boolean;
  accessError: 'network' | null;
  canEdit: boolean;
  isAdmin: boolean;
}

const ProtectedAreaContext = createContext<ProtectedAreaContextValue | null>(
  null,
);

export function ProtectedAreaProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const [unlockedState, setUnlockedState] = useState(false);
  const [roleState, setRoleState] = useState<'admin' | 'contributor' | null>(
    null,
  );
  const queryClient = useQueryClient();

  const {
    data: requiresResult,
    isLoading: isLoadingRequires,
    isError: requiresError,
  } = useQuery({
    queryKey: queryKeys.settings.requiresPassword,
    queryFn: fetchSettingsRequiresPassword,
    retry: 1,
  });

  // При ошибке или отсутствии ответа — считаем пароль нужен (показываем диалог)
  const requiresPassword =
    requiresResult?.requires === true ||
    !!requiresError ||
    (requiresResult === undefined && !isLoadingRequires);
  const hasContributorTier = requiresResult?.has_contributor_tier === true;

  const { data: checkResult, isLoading: isLoadingAccess } = useQuery({
    queryKey: queryKeys.settings.checkAccess,
    queryFn: checkSettingsAccess,
    enabled: !!requiresPassword,
    retry: false,
    staleTime: 60_000,
    gcTime: 5 * 60_000,
  });

  const setUnlocked = useCallback(
    (value: boolean, role?: 'admin' | 'contributor') => {
      setUnlockedState(value);
      setRoleState(value && role ? role : null);
      queryClient.invalidateQueries({
        queryKey: queryKeys.settings.checkAccess,
      });
      queryClient.invalidateQueries({ queryKey: queryKeys.settings.all });
    },
    [queryClient],
  );

  const logoutAccess = useCallback(async () => {
    try {
      await logoutSettingsSession();
    } finally {
      setUnlockedState(false);
      setRoleState(null);
      queryClient.invalidateQueries({
        queryKey: queryKeys.settings.checkAccess,
      });
      queryClient.invalidateQueries({ queryKey: queryKeys.settings.all });
    }
  }, [queryClient]);

  /**
   * После verify-password `invalidateQueries(check-access)` ещё не вернулся, а в кэше
   * может лежать старая сессия (например contributor) — тогда нельзя брать роль только
   * из checkResult: иначе isAdmin остаётся false и «Станция» не открывается.
   * Пока локально разблокировали с паролем — доверяем roleState до прихода свежего check-access.
   */
  const serverRole: 'admin' | 'contributor' | null =
    checkResult?.unlocked === true
      ? ('role' in checkResult ? checkResult.role : undefined) || 'admin'
      : null;
  const role =
    unlockedState && roleState != null ? roleState : serverRole;

  const unlocked =
    !requiresPassword ||
    (requiresPassword && (checkResult?.unlocked === true || unlockedState));

  const canEdit =
    unlocked &&
    (role === 'admin' || role === 'contributor' || !hasContributorTier);
  const isAdmin = unlocked && (role === 'admin' || !hasContributorTier);

  const accessError =
    requiresPassword && checkResult?.unlocked === false && checkResult?.error
      ? 'network'
      : null;
  const isLoading =
    isLoadingRequires || (!!requiresPassword && isLoadingAccess);

  const value = useMemo<ProtectedAreaContextValue>(
    () => ({
      requiresPassword: !!requiresPassword,
      hasContributorTier,
      unlocked,
      role: unlocked ? role || 'admin' : null,
      setUnlocked,
      logoutAccess,
      isLoading,
      accessError,
      canEdit,
      isAdmin,
    }),
    [
      requiresPassword,
      hasContributorTier,
      unlocked,
      role,
      setUnlocked,
      logoutAccess,
      isLoading,
      accessError,
      canEdit,
      isAdmin,
    ],
  );

  return (
    <ProtectedAreaContext.Provider value={value}>
      {children}
    </ProtectedAreaContext.Provider>
  );
}

export function useProtectedArea() {
  const ctx = useContext(ProtectedAreaContext);
  if (!ctx) {
    throw new Error(
      'useProtectedArea must be used within ProtectedAreaProvider',
    );
  }
  return ctx;
}
