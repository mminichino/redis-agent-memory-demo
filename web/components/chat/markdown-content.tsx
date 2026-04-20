"use client";

import ReactMarkdown from "react-markdown";
import rehypeSanitize from "rehype-sanitize";
import remarkBreaks from "remark-breaks";
import remarkEmoji from "remark-emoji";
import remarkGfm from "remark-gfm";
import { cn } from "@/lib/utils";

type MarkdownContentProps = {
  /** Markdown source (Unicode emoji and `:shortcode:` supported). */
  markdown: string;
  className?: string;
};

export function MarkdownContent({ markdown, className }: MarkdownContentProps) {
  const trimmed = markdown.trim();
  if (!trimmed) {
    return <p className="text-sm text-muted">(no visible content)</p>;
  }

  return (
    <div
      className={cn(
        "prose prose-invert max-w-none text-sm leading-relaxed",
        "prose-headings:scroll-mt-4 prose-headings:font-semibold prose-headings:text-foreground",
        "prose-p:text-foreground prose-li:text-foreground",
        "prose-a:text-brand prose-a:no-underline hover:prose-a:underline",
        "prose-code:rounded-md prose-code:bg-canvas prose-code:px-1.5 prose-code:py-0.5 prose-code:font-mono prose-code:text-[13px] prose-code:text-foreground prose-code:before:content-none prose-code:after:content-none",
        "prose-pre:bg-canvas prose-pre:border prose-pre:border-border prose-pre:text-[13px]",
        "prose-blockquote:border-border prose-blockquote:text-muted",
        "prose-strong:text-foreground prose-table:text-foreground",
        className
      )}
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkBreaks, remarkEmoji]}
        rehypePlugins={[rehypeSanitize]}
      >
        {trimmed}
      </ReactMarkdown>
    </div>
  );
}
