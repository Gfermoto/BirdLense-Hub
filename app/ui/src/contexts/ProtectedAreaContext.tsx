import React, {
  createContext,
  useContext,
  useCallback,
  useState,
  useMemo,
} from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  fetchSettingsRequiresPassword,
  checkSettingsAccess,
} from '../api/api';

interface ProtectedAreaContextValue {
  requiresPassword: boolean;
  unlocked: boolean;
  setUnlocked: (value: boolean) => void;
  isLoading: boolean;
  accessError: 'network' | null;
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

  const { data: requiresPassword, isLoading: isLoadingRequires } = useQuery({
    queryKey: ['settings-requires-password'],
    queryFn: fetchSettingsRequiresPassword,
  });

  const { data: checkResult, isLoading: isLoadingAccess } = useQuery({
    queryKey: ['settings-check-access'],
    queryFn: checkSettingsAccess,
    enabled: !!requiresPassword,
    retry: false,
  });

  const setUnlocked = useCallback((value: boolean) => {
    setUnlockedState(value);
  }, []);

  const unlocked =
    requiresPassword === false
      ? true
      : requiresPassword === true
        ? (unlockedState || checkResult?.unlocked === true)
        : false;
  const accessError =
    requiresPassword && checkResult?.unlocked === false && checkResult?.error
      ? 'network'
      : null;
  const isLoading =
    isLoadingRequires || (!!requiresPassword && isLoadingAccess);

  const value = useMemo<ProtectedAreaContextValue>(
    () => ({
      requiresPassword: !!requiresPassword,
      unlocked,
      setUnlocked,
      isLoading,
      accessError,
    }),
    [requiresPassword, unlocked, setUnlocked, isLoading, accessError],
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
