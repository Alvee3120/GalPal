import { Fragment } from "react";
import Link from "next/link";

// Renders the CMS content format (apps.content.models.Page.content — a small Markdown subset) as plain React
// elements. Nothing is ever injected as HTML, so whatever an editor types can't run as script:
//   ## Heading / ### Sub-heading     - bullet / * bullet     1. numbered     **bold**     [text](/path or https://…)
// A blank line starts a new paragraph. With `sectioned`, each "## Heading" opens a <section> (the .legal-page layout).

const SAFE_HREF = /^(\/(?!\/)|https?:\/\/|mailto:|tel:)/i;

function inline(text, keyPrefix) {
  const out = [];
  const pattern = /\*\*(.+?)\*\*|\[([^\]]+)\]\(([^)\s]+)\)/g;
  let last = 0;
  let match;
  let i = 0;
  while ((match = pattern.exec(text))) {
    if (match.index > last) out.push(text.slice(last, match.index));
    const key = `${keyPrefix}-${i++}`;
    if (match[1] !== undefined) {
      out.push(<strong key={key}>{match[1]}</strong>);
    } else {
      const [, , label, href] = match;
      if (!SAFE_HREF.test(href)) out.push(label);
      else if (href.startsWith("/")) out.push(<Link key={key} href={href}>{label}</Link>);
      else out.push(<a key={key} href={href} target={/^https?:/i.test(href) ? "_blank" : undefined} rel="noopener noreferrer">{label}</a>);
    }
    last = pattern.lastIndex;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

export function parseBlocks(text) {
  const blocks = [];
  let para = [];
  let list = null;
  const flushPara = () => {
    if (para.length) blocks.push({ type: "p", text: para.join(" ") });
    para = [];
  };
  const flushList = () => {
    if (list) blocks.push(list);
    list = null;
  };
  for (const raw of (text ?? "").replace(/\r\n?/g, "\n").split("\n")) {
    const line = raw.trim();
    let m;
    if (!line) {
      flushPara();
      flushList();
    } else if ((m = /^(#{2,3})\s+(.*)$/.exec(line))) {
      flushPara();
      flushList();
      blocks.push({ type: m[1].length === 2 ? "h2" : "h3", text: m[2] });
    } else if ((m = /^[-*]\s+(.*)$/.exec(line)) || (m = /^\d+[.)]\s+(.*)$/.exec(line))) {
      flushPara();
      const type = /^\d/.test(line) ? "ol" : "ul";
      if (list && list.type !== type) flushList();
      list ??= { type, items: [] };
      list.items.push(m[1]);
    } else {
      flushList();
      para.push(line.replace(/^#\s+/, ""));
    }
  }
  flushPara();
  flushList();
  return blocks;
}

function Block({ block, k }) {
  switch (block.type) {
    case "h2":
      return <h2>{inline(block.text, k)}</h2>;
    case "h3":
      return <h3>{inline(block.text, k)}</h3>;
    case "ul":
    case "ol": {
      const List = block.type;
      return (
        <List>
          {block.items.map((item, i) => (
            <li key={i}>{inline(item, `${k}-${i}`)}</li>
          ))}
        </List>
      );
    }
    default:
      return <p>{inline(block.text, k)}</p>;
  }
}

export default function RichText({ text, sectioned = false }) {
  const blocks = parseBlocks(text);
  if (!sectioned) {
    return blocks.map((block, i) => <Block key={i} block={block} k={`b${i}`} />);
  }
  const sections = [];
  for (const block of blocks) {
    if (block.type === "h2" || sections.length === 0) sections.push([]);
    sections[sections.length - 1].push(block);
  }
  return sections.map((section, s) => (
    <section key={s}>
      {section.map((block, i) => (
        <Fragment key={i}>
          <Block block={block} k={`s${s}b${i}`} />
        </Fragment>
      ))}
    </section>
  ));
}
