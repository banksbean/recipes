// Word exports of the recipe collection, built from the repo's source files.
// The repo (recipes/<collection>/<id>.json) is the master copy; these .docx files are read-only exports.
// Usage: node export.js            (writes exports/*.docx)
// build.py build runs this automatically after a successful build.
const fs = require("fs"), path = require("path");
const {
  Document, Packer, Paragraph, TextRun, ExternalHyperlink, HeadingLevel, AlignmentType,
  LevelFormat, PageBreak, TableOfContents, Footer, PageNumber,
} = require("docx");

const ROOT = __dirname;
const OUT = path.join(ROOT, "exports");
const COLS = JSON.parse(fs.readFileSync(path.join(ROOT, "collections.json"), "utf8"));
const load = col => {
  const d = path.join(ROOT, "recipes", col);
  if (!fs.existsSync(d)) return [];
  return fs.readdirSync(d).filter(f => f.endsWith(".json")).sort()
    .map(f => JSON.parse(fs.readFileSync(path.join(d, f), "utf8")))
    .filter(r => !r.hidden)
    .sort((a, b) => (a.sort ?? 1e9) - (b.sort ?? 1e9) || a.title.localeCompare(b.title));
};

const FONT = "Arial", ACC = "4F7A12", BROWN = "692C02", GRAY = "7A7A7A";
const styles = {
  default: { document: { run: { font: FONT, size: 22 } } },
  paragraphStyles: [
    { id: "Title", name: "Title", basedOn: "Normal", next: "Normal", run: { font: FONT, size: 44, bold: true, color: BROWN },
      paragraph: { spacing: { before: 0, after: 120 } } },
    { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
      run: { font: FONT, size: 32, bold: true, color: ACC },
      paragraph: { spacing: { before: 240, after: 120 }, keepNext: true, outlineLevel: 0 } },
    { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
      run: { font: FONT, size: 28, bold: true, color: BROWN },
      paragraph: { spacing: { before: 360, after: 60 }, keepNext: true, outlineLevel: 1,
        border: { bottom: { style: "single", size: 8, color: ACC, space: 2 } } } },
  ],
};
const numbering = { config: [{ reference: "b", levels: [
  { level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 270 } } } },
  { level: 1, format: LevelFormat.BULLET, text: "◦", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 1080, hanging: 270 } } } },
] }] };

const P = (children, opts = {}) => new Paragraph({ children, spacing: { after: 40 }, ...opts });
const T = (text, o = {}) => new TextRun({ text, ...o });
const link = (text, url) => new ExternalHyperlink({ link: url, children: [T(text, { style: "Hyperlink", color: ACC, underline: {} })] });
const bullet = (text, level = 0) => {
  const t = String(text), isLabel = t.trim().endsWith(":"), isNote = t.trim().startsWith("[");
  return P([T(t, { italics: isLabel || isNote, color: isNote ? GRAY : undefined })], { numbering: { reference: "b", level } });
};
const items = (list, out) => {
  for (const it of list || []) {
    if (typeof it === "string") { out.push(bullet(it)); continue; }
    out.push(bullet(it.text));
    for (const s of it.sub || []) out.push(bullet(typeof s === "string" ? s : s.text, 1));
  }
};
const action = text => P([T(text, { bold: true, color: BROWN })], { spacing: { before: 140, after: 40 }, keepNext: true });

function recipe(r, conventions) {
  const out = [new Paragraph({ heading: HeadingLevel.HEADING_2, children: [T(r.title)] })];
  const meta = [];
  if (r.source && r.source.text) {
    meta.push(T("Source: ", { bold: true }));
    meta.push(r.source.url ? link(r.source.text, r.source.url) : T(r.source.text));
  }
  if (r.makes) { if (meta.length) meta.push(T("  ·  ")); meta.push(T("Makes: ", { bold: true }), T(r.makes)); }
  if (r.beans) { if (meta.length) meta.push(T("  ·  ")); meta.push(T("Beans: ", { bold: true }), T(r.beans)); }
  if (meta.length) out.push(P(meta));
  const added = [r.added && `Added ${r.added}`, r.origin].filter(Boolean).join(" · ");
  if (added) out.push(P([T(added, { size: 18, color: GRAY })]));
  if (r.description) out.push(P([T(r.description, { italics: true })], { spacing: { before: 80, after: 40 } }));
  for (const s of r.steps) {
    if (s.table) {
      for (const c of s.table) {
        out.push(P([c.url ? link(c.title, c.url) : T(c.title, { bold: true })], { spacing: { before: 140, after: 20 }, keepNext: true }));
        if (c.action) out.push(action(c.action));
        items(c.items, out);
      }
    } else if (s.action) { out.push(action(s.action)); items(s.items, out); }
    else if (s.text) out.push(P([T(s.text, { italics: true })], { spacing: { before: 140, after: 40 } }));
  }
  const notes = (r.notes || []).map(n => typeof n === "string" ? n : `${n.kind || "Note"} (${n.d || "undated"}): ${n.text}`);
  if (notes.length) {
    out.push(P([T("Notes", { bold: true, color: ACC })], { spacing: { before: 160, after: 40 } }));
    notes.forEach(n => out.push(bullet(n)));
  }
  for (const e of r.edits || []) out.push(P([T(`[${e}]`, { color: GRAY, size: 18 })]));
  return out;
}

function book(file, title, subtitle, groups) {
  const body = [
    new Paragraph({ style: "Title", children: [T(title)] }),
    P([T(subtitle, { color: GRAY })]),
    P([T(`Exported ${new Date().toISOString().slice(0, 10)} from github.com/banksbean/recipes (the master copy). Edit recipes there, not in this file.`, { size: 18, color: GRAY })]),
    new TableOfContents("Contents", { hyperlink: true, headingStyleRange: "1-2" }),
  ];
  let n = 0;
  for (const g of groups) {
    if (g.conventions && g.conventions.length) {
      body.push(new Paragraph({ children: [new PageBreak()] }));
      body.push(new Paragraph({ heading: HeadingLevel.HEADING_1, children: [T("Book conventions")] }));
      g.conventions.forEach(c => body.push(bullet(c)));
    }
    const bySec = new Map();
    for (const r of g.recipes) { if (!bySec.has(r.section)) bySec.set(r.section, []); bySec.get(r.section).push(r); }
    for (const [sec, rs] of bySec) {
      body.push(new Paragraph({ children: [new PageBreak()] }));
      body.push(new Paragraph({ heading: HeadingLevel.HEADING_1, children: [T(g.prefix ? `${g.prefix}: ${sec}` : sec)] }));
      for (const r of rs) { body.push(...recipe(r)); n++; }
    }
  }
  const doc = new Document({
    creator: "banksbean/recipes", title, styles, numbering, features: { updateFields: true },
    sections: [{
      properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1080, bottom: 1080, left: 1080, right: 1080 } } },
      footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER,
        children: [T(title + "  ·  ", { size: 16, color: GRAY }), new TextRun({ children: [PageNumber.CURRENT], size: 16, color: GRAY })] })] }) },
      children: body,
    }],
  });
  return Packer.toBuffer(doc).then(buf => { fs.writeFileSync(path.join(OUT, file), buf); return `${file}: ${n} entries`; });
}

fs.mkdirSync(OUT, { recursive: true });
const raza = COLS.find(c => c.id === "raza") || {};
Promise.all([
  book("All Recipes.docx", "All Recipes", "House recipes: Mexican, Oaxacan and everything else.", [{ recipes: load("house") }]),
  book("Pakistani & North Indian Cooking (Raza).docx", "Pakistani & North Indian Cooking", raza.blurb || "", [{ recipes: load("raza"), conventions: raza.conventions }]),
  book("Bean Recipes v2.docx", "Bean Recipes v2", "Instant Pot first, plus stovetop, oven and cold bean salads.",
    [{ recipes: load("guides"), prefix: "Guides" }, { recipes: load("beans") }]),
]).then(r => r.forEach(x => console.log("Wrote exports/" + x)))
  .catch(e => { console.error(e); process.exit(1); });
