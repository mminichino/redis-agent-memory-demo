"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode
} from "react";

const ChatHealthContext = createContext<{
  hasError: boolean;
  setHasError: (value: boolean) => void;
} | null>(null);

export function ChatHealthProvider({ children }: { children: ReactNode }) {
  const [hasError, setHasError] = useState(false);
  return (
    <ChatHealthContext.Provider value={{ hasError, setHasError }}>
      {children}
    </ChatHealthContext.Provider>
  );
}

export function useSyncChatErrorState(hasError: boolean) {
  const ctx = useContext(ChatHealthContext);
  useEffect(() => {
    if (!ctx) return;
    ctx.setHasError(hasError);
    return () => ctx.setHasError(false);
  }, [ctx, hasError]);
}

export function useAppShellSessionStatus() {
  const ctx = useContext(ChatHealthContext);
  const hasError = ctx?.hasError ?? false;
  return hasError ? ("attention" as const) : ("healthy" as const);
}
