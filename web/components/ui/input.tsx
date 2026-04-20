"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

type InputProps = React.InputHTMLAttributes<HTMLInputElement> & {
  error?: string;
};

export function Input({ className, error, ...props }: InputProps) {
  return (
    <div>
      <input
        className={cn(
          "h-10 w-full rounded-md border border-border bg-panel px-3 text-sm text-foreground outline-none transition placeholder:text-muted focus:border-blue-400 focus:ring-2 focus:ring-blue-500/25",
          error && "border-danger focus:border-danger focus:ring-red-500/30",
          className
        )}
        {...props}
      />
      {error ? (
        <p className="mt-1 text-xs text-red-400" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}
