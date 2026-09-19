/**
 * SatQuery AI — Markdown Parser & Formatter
 * Formats LLM responses and scientific findings into rich, structured HTML.
 */

function escapeHtml(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function formatInline(text: string): string {
  let res = text;
  // Bold + Italic (***text*** or ___text___)
  res = res.replace(/\*\*\*(.*?)\*\*\*/g, '<strong><em>$1</em></strong>');
  res = res.replace(/___(.*?)___/g, '<strong><em>$1</em></strong>');

  // Bold (**text** or __text__)
  res = res.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  res = res.replace(/__(.*?)__/g, '<strong>$1</strong>');

  // Italic (*text* or _text_)
  res = res.replace(/\*([^*]+)\*/g, '<em>$1</em>');
  res = res.replace(/_([^_]+)_/g, '<em>$1</em>');

  // Strikethrough (~~text~~)
  res = res.replace(/~~(.*?)~~/g, '<del>$1</del>');

  // Inline code (`code`)
  res = res.replace(/`([^`]+)`/g, '<code class="md-inline-code">$1</code>');

  return res;
}

export function parseMarkdown(rawMd: string): string {
  if (!rawMd) return '';

  // Standardize newlines
  const text = rawMd.replace(/\r\n/g, '\n').replace(/\r/g, '\n');

  // Extract fenced code blocks first to protect them
  const codeBlocks: string[] = [];
  const placeholder = '___CODE_BLOCK_PLACEHOLDER_';
  const textWithoutCode = text.replace(/```([a-zA-Z0-9_-]*)\n([\s\S]*?)```/g, (_, lang, code) => {
    const idx = codeBlocks.length;
    const escapedCode = escapeHtml(code.trimEnd());
    const langBadge = lang ? `<span class="md-code-lang">${escapeHtml(lang)}</span>` : '';
    codeBlocks.push(
      `<div class="md-code-block">${langBadge}<pre class="md-code"><code>${escapedCode}</code></pre></div>`
    );
    return `${placeholder}${idx}___`;
  });

  // Split into block sections by double newline
  const rawBlocks = textWithoutCode.split(/\n\s*\n/);
  const renderedBlocks: string[] = [];

  for (const block of rawBlocks) {
    const trimmed = block.trim();
    if (!trimmed) continue;

    // Check code block placeholder
    if (trimmed.startsWith(placeholder)) {
      const idxMatch = trimmed.match(/___CODE_BLOCK_PLACEHOLDER_(\d+)___/);
      if (idxMatch) {
        renderedBlocks.push(codeBlocks[parseInt(idxMatch[1], 10)]);
        continue;
      }
    }

    // Horizontal Rule
    if (/^(?:---|\*\*\*|___)$/.test(trimmed)) {
      renderedBlocks.push('<hr class="md-hr" />');
      continue;
    }

    // Blockquote / Note Callout
    if (trimmed.startsWith('>')) {
      const quoteLines = trimmed.split('\n').map((l) => l.replace(/^>\s?/, ''));
      const quoteContent = formatInline(escapeHtml(quoteLines.join(' ')));
      const isNote = /note|important|warning|caution/i.test(quoteContent);
      renderedBlocks.push(
        `<blockquote class="md-quote ${isNote ? 'md-callout' : ''}">${quoteContent}</blockquote>`
      );
      continue;
    }

    // Markdown Table
    if (trimmed.includes('|') && trimmed.split('\n').some((l) => /^\s*\|?\s*:?-+:?\s*\|/.test(l))) {
      const tableLines = trimmed.split('\n').filter((l) => l.includes('|'));
      if (tableLines.length >= 2) {
        let thead = '';
        let tbody = '';
        let isHeader = true;

        for (let i = 0; i < tableLines.length; i++) {
          const rowLine = tableLines[i].trim();
          // Separator row (e.g. |---|---|)
          if (/^\|?\s*:?-+:?\s*\|/.test(rowLine)) {
            isHeader = false;
            continue;
          }
          const cells = rowLine
            .replace(/^\|/, '')
            .replace(/\|$/, '')
            .split('|')
            .map((c) => formatInline(escapeHtml(c.trim())));

          if (isHeader) {
            thead += `<tr>${cells.map((c) => `<th>${c}</th>`).join('')}</tr>`;
          } else {
            tbody += `<tr>${cells.map((c) => `<td>${c}</td>`).join('')}</tr>`;
          }
        }
        renderedBlocks.push(
          `<div class="md-table-wrapper"><table class="md-table">${thead ? `<thead>${thead}</thead>` : ''}<tbody>${tbody}</tbody></table></div>`
        );
        continue;
      }
    }

    // Headings (if whole block is a single heading or starts with one)
    if (/^#{1,6}\s+/.test(trimmed)) {
      const headingLines = trimmed.split('\n');
      const formattedHeadings: string[] = [];
      let remainder: string[] = [];

      for (let i = 0; i < headingLines.length; i++) {
        const line = headingLines[i].trim();
        const match = line.match(/^(#{1,6})\s+(.*)$/);
        if (match) {
          const level = match[1].length;
          const hTag = level === 1 ? 'h2' : level === 2 ? 'h3' : level === 3 ? 'h4' : 'h5';
          const content = formatInline(escapeHtml(match[2]));
          formattedHeadings.push(`<${hTag} class="md-${hTag}">${content}</${hTag}>`);
        } else {
          remainder.push(line);
        }
      }

      if (formattedHeadings.length > 0) {
        renderedBlocks.push(formattedHeadings.join('\n'));
      }
      if (remainder.length > 0) {
        const pContent = formatInline(escapeHtml(remainder.join(' ')));
        renderedBlocks.push(`<p class="md-p">${pContent}</p>`);
      }
      continue;
    }

    // Unordered List (- or *)
    if (/^(\s*[-*]\s+)/.test(trimmed)) {
      const items = trimmed.split('\n');
      let listHtml = '<ul class="md-ul">';
      for (const item of items) {
        const cleanItem = item.replace(/^\s*[-*]\s+/, '').trim();
        if (!cleanItem) continue;
        const itemContent = formatInline(escapeHtml(cleanItem));
        listHtml += `<li class="md-li">${itemContent}</li>`;
      }
      listHtml += '</ul>';
      renderedBlocks.push(listHtml);
      continue;
    }

    // Ordered List (1. 2.)
    if (/^(\s*\d+\.\s+)/.test(trimmed)) {
      const items = trimmed.split('\n');
      let listHtml = '<ol class="md-ol">';
      for (const item of items) {
        const cleanItem = item.replace(/^\s*\d+\.\s+/, '').trim();
        if (!cleanItem) continue;
        const itemContent = formatInline(escapeHtml(cleanItem));
        listHtml += `<li class="md-li">${itemContent}</li>`;
      }
      listHtml += '</ol>';
      renderedBlocks.push(listHtml);
      continue;
    }

    // Standard Paragraph
    const lines = trimmed.split('\n').map((l) => formatInline(escapeHtml(l.trim())));
    const pContent = lines.join(' ');
    renderedBlocks.push(`<p class="md-p">${pContent}</p>`);
  }

  return renderedBlocks.join('\n');
}
