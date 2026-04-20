"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
};

const styles: Record<NonNullable<ButtonProps["variant"]>, string> = {
  primary:
    "bg-brand text-white hover:bg-blue-500 focus-visible:outline-blue-300",
  secondary:
    "bg-panelMuted text-foreground border border-border hover:bg-slate-700/60 focus-visible:outline-slate-300",
  ghost:
    "bg-transparent text-foreground hover:bg-panelMuted focus-visible:outline-slate-300",
  danger:
    "bg-danger text-white hover:bg-red-500 focus-visible:outline-red-200"
};

export function Button({
  className,
  variant = "primary",
  type = "button",
  ...props
}: ButtonProps) {
  return (
    <button
      type={type}
      className={cn(
        "inline-flex h-10 items-center justify-center rounded-md px-4 text-sm font-medium transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 disabled:cursor-not-allowed disabled:opacity-60",
        styles[variant],
        className
      )}
      {...props}
    />
  );
}
