import React, {
  createContext,
  useContext,
  useCallback,
  useState,
  useMemo,
} from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  fetchSettingsRequiresPassword,
  checkSettingsAccess,
} from '../api/api';

interface ProtectedAreaContextValue {
  requiresPassword: boolean;
  hasContributorTier: boolean;
  unlocked: boolean;
  role: 'admin' | 'contributor' | null;
  setUnlocked: (value: boolean, role?: 'admin' | 'contributor') => void;
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
  const [roleState, setRoleState] = useState<'admin' | 'contributor' | null>(null);
  const queryClient = useQueryClient();

  const { data: requiresResult, isLoading: isLoadingRequires, isError: requiresError } = useQuery({
    queryKey: ['settings-requires-password'],
    queryFn: fetchSettingsRequiresPassword,
    retry: 1,
  });

  // При ошибке или отсутствии ответа — считаем пароль нужен (показываем диалог)
  const requiresPassword =
    requiresResult?.requires === true ||
    (!!requiresError || (requiresResult === undefined && !isLoadingRequires));
  const hasContributorTier = requiresResult?.has_contributor_tier === true;

  const { data: checkResult, isLoading: isLoadingAccess } = useQuery({
    queryKey: ['settings-check-access'],
    queryFn: checkSettingsAccess,
    enabled: !!requiresPassword,
    retry: false,
    staleTime: 60_000,
    gcTime: 5 * 60_000,
  });

  const setUnlocked = useCallback((value: boolean, role?: 'admin' | 'contributor') => {
    setUnlockedState(value);
    setRoleState(value && role ? role : null);
    if (value) {
      queryClient.invalidateQueries({ queryKey: ['settings-check-access'] });
      queryClient.invalidateQueries({ queryKey: ['settings'] });
    }
  }, [queryClient]);

  const role =
    checkResult?.unlocked && 'role' in checkResult
      ? (checkResult.role || 'admin')
      : roleState;

  const unlocked =
    !requiresPassword ||
    (requiresPassword && (checkResult?.unlocked === true || unlockedState));

  const canEdit = unlocked && (role === 'admin' || role === 'contributor' || !hasContributorTier);
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
      role: unlocked ? (role || 'admin') : null,
      setUnlocked,
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
    throw new Error('useProtectedArea must be used within ProtectedAreaProvider');
  }
  return ctx;
}
