import { cn } from "@/lib/utils";

function InlineMd({ text }: { text: string }) {
  const parts: React.ReactNode[] = [];
  const regex = /\*\*([^*]+)\*\*|\*([^*]+)\*|`([^`]+)`|\[([^\]]+)\]\(([^)]+)\)/g;
  let lastIndex = 0;
  let match;
  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) parts.push(text.slice(lastIndex, match.index));
    if (match[1] !== undefined) {
      parts.push(
        <strong key={match.index} className="font-semibold text-[#ECECEC]">
          {match[1]}
        </strong>,
      );
    } else if (match[2] !== undefined) {
      parts.push(
        <em key={match.index} className="italic text-[#ECECEC]/85">
          {match[2]}
        </em>,
      );
    } else if (match[3] !== undefined) {
      parts.push(
        <code
          key={match.index}
          className="rounded-md bg-white/[0.08] px-1.5 py-0.5 font-mono text-[0.8125rem] text-emerald-200/90"
        >
          {match[3]}
        </code>,
      );
    } else if (match[4] !== undefined && match[5] !== undefined) {
      parts.push(
        <a
          key={match.index}
          href={match[5]}
          target="_blank"
          rel="noreferrer"
          className="text-emerald-300/90 underline decoration-emerald-400/30 underline-offset-2 hover:text-emerald-200"
        >
          {match[4]}
        </a>,
      );
    }
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < text.length) parts.push(text.slice(lastIndex));
  return <>{parts}</>;
}

interface MarkdownProps {
  text: string;
  className?: string;
  /** Compact mode for lists / secondary notes */
  dense?: boolean;
}

/**
 * Lightweight markdown renderer for Aurora chat prose.
 * Supports: paragraphs, headings, lists, hr, bold/italic/code/links.
 */
export function Markdown({ text, className, dense = false }: MarkdownProps) {
  const lines = text.replace(/\r\n/g, "\n").split("\n");
  const blocks: React.ReactNode[] = [];
  let i = 0;
  let key = 0;

  while (i < lines.length) {
    const raw = lines[i];
    const line = raw.trimEnd();
    const trimmed = line.trim();

    if (!trimmed) {
      i += 1;
      continue;
    }

    if (trimmed === "---" || trimmed === "***") {
      blocks.push(<hr key={key++} className="my-4 border-white/[0.08]" />);
      i += 1;
      continue;
    }

    const heading = /^(#{1,3})\s+(.+)$/.exec(trimmed);
    if (heading) {
      const level = heading[1].length;
      const content = heading[2];
      const cls =
        level === 1
          ? "text-[1.25rem] font-semibold tracking-tight text-white/95"
          : level === 2
            ? "text-[1.125rem] font-semibold tracking-tight text-white/92"
            : "text-[1rem] font-semibold text-white/90";
      blocks.push(
        <p key={key++} className={cn(cls, dense ? "mt-2 mb-1" : "mt-3 mb-1.5")}>
          <InlineMd text={content} />
        </p>,
      );
      i += 1;
      continue;
    }

    if (/^[-*•]\s+/.test(trimmed) || /^\d+\.\s+/.test(trimmed)) {
      const items: string[] = [];
      while (i < lines.length) {
        const t = lines[i].trim();
        if (!t) break;
        const m = /^[-*•]\s+(.+)$/.exec(t) || /^\d+\.\s+(.+)$/.exec(t);
        if (!m) break;
        items.push(m[1]);
        i += 1;
      }
      blocks.push(
        <ul
          key={key++}
          className={cn(
            "my-2 list-disc space-y-1.5 pl-5 marker:text-white/30",
            dense && "my-1 space-y-1 text-[0.875rem]",
          )}
        >
          {items.map((item, idx) => (
            <li key={idx} className="leading-7 text-white/[0.82]">
              <InlineMd text={item} />
            </li>
          ))}
        </ul>,
      );
      continue;
    }

    if (trimmed.startsWith("> ")) {
      const quote: string[] = [];
      while (i < lines.length && lines[i].trim().startsWith("> ")) {
        quote.push(lines[i].trim().replace(/^>\s?/, ""));
        i += 1;
      }
      blocks.push(
        <blockquote
          key={key++}
          className="my-3 border-l-2 border-emerald-500/40 pl-3 text-white/70"
        >
          <InlineMd text={quote.join(" ")} />
        </blockquote>,
      );
      continue;
    }

    // Paragraph: merge consecutive non-empty plain lines
    const para: string[] = [trimmed];
    i += 1;
    while (i < lines.length) {
      const t = lines[i].trim();
      if (
        !t ||
        t === "---" ||
        /^#{1,3}\s+/.test(t) ||
        /^[-*•]\s+/.test(t) ||
        /^\d+\.\s+/.test(t) ||
        t.startsWith("> ")
      ) {
        break;
      }
      para.push(t);
      i += 1;
    }
    blocks.push(
      <p
        key={key++}
        className={cn(
          "text-[15px] leading-[1.8] text-[#ECECEC]/90 tracking-[0.01em]",
          dense && "text-[0.875rem] leading-[1.65] text-[#A0A0A0]",
        )}
      >
        <InlineMd text={para.join(" ")} />
      </p>,
    );
  }

  return (
    <div className={cn("aurora-md space-y-3.5", className)}>{blocks}</div>
  );
}

export function MarkdownInline({ text }: { text: string }) {
  return <InlineMd text={text} />;
}
