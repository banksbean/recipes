#!/usr/bin/env python3
"""Build data/recipes.json for the recipe site from the per-recipe source files.

Commands
  python3 -I build.py build [--expect N]
      Read collections.json and every recipes/<collection>/<id>.json, parse each
      ingredient line into quantity / unit / item, and write data/recipes.json.
      --expect N fails the build unless exactly N recipes (guides not counted) were written.

  python3 -I build.py import --house H.json --raza R.json --beans B.json
      Sync from the Google Drive archive (the data.js files behind All Recipes.docx,
      the Raza docx and Bean Recipes v2.docx). Each argument is a JSON dump of one
      data.js file (see README). Creates or updates recipes/<collection>/<id>.json.
      Site-only fields already in a source file (tags, prep_min, cook_min, hidden)
      are kept; recipe content is replaced by the archive version.

Only the standard library is used.
"""
import argparse, glob, json, os, re, sys, unicodedata
from datetime import date

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(ROOT, "recipes")
OUT = os.path.join(ROOT, "data", "recipes.json")
COLLECTIONS = os.path.join(ROOT, "collections.json")
TAG_KEYS = ("cuisine", "course", "protein", "season")

# ---------------------------------------------------------------- parsing
FRAC = {"½": .5, "⅓": 1/3, "⅔": 2/3, "¼": .25, "¾": .75, "⅛": .125, "⅜": .375, "⅝": .625, "⅞": .875}
FR = "".join(FRAC)
NUM = rf"(?:\d+\s+\d+/\d+|\d+[{FR}]|\d+/\d+|\d+(?:\.\d+)?|[{FR}])"
UNITS = {
    "tbsp": "Tbsp", "tbs": "Tbsp", "tablespoon": "Tbsp", "tablespoons": "Tbsp",
    "tsp": "tsp", "teaspoon": "tsp", "teaspoons": "tsp",
    "cup": "cup", "cups": "cup", "lb": "lb", "lbs": "lb", "pound": "lb", "pounds": "lb",
    "oz": "oz", "ounce": "oz", "ounces": "oz", "fl oz": "fl oz",
    "g": "g", "kg": "kg", "ml": "ml", "l": "L", "qt": "qt", "quart": "qt", "quarts": "qt",
    "pint": "pint", "pints": "pint", "in": "in", "inch": "in", "inches": "in", "cm": "cm", "mm": "mm",
}
UNIT_RE = r"(?:fl oz|tablespoons?|teaspoons?|tbsp|tbs|tsp|cups?|lbs?|pounds?|ounces?|oz|kg|g|ml|l|quarts?|qt|pints?|inch(?:es)?|in|cm|mm)"
QTY_RE = re.compile(rf"^(about\s+|up to\s+)?({NUM})(?:\s*(?:to|-|–)\s*({NUM}))?\s*(?:({UNIT_RE})\b\.?)?\s*(.*)$", re.I)
ALT_RE = re.compile(rf"\s*\((?:about\s+)?({NUM})(?:\s*(?:to|-|–)\s*({NUM}))?\s*({UNIT_RE})(?:\)|;\s*([^)]*)\))", re.I)
LENGTH = {"in", "cm", "mm"}
US = {"Tbsp", "tsp", "cup", "lb", "oz", "fl oz", "qt", "pint", "in"}
METRIC = {"g", "kg", "ml", "L", "cm", "mm"}

REF_RE = re.compile(
    r"^(all |reserved|remaining|browned|blended|cooked |drained|seared|seasoned|marinated|marinade$|soaked|"
    r"rinsed|floured|ground spices|sauteed|mole paste|green paste|coconut paste|chile-shrimp|boiled potatoes|"
    r"roasted (tomatoes|coconut)|half of:|toasted cumin|shrimp shells|bok choy (leaves|stems)$|chopped anchos|"
    r"red chile sauce|meat on a platter|mushrooms on top|toasted bread on top|poblano strips|cooked corn|"
    r"drained yogurt|rinsed rice|sweet heavy soy)", re.I)
NOTE_RE = re.compile(
    r"^(add |cook |lay |flip |overlap |peel |stack |grind |discard |refrigerate |nudge |uncover|meanwhile|if |"
    r"when |in |in an |or |no |more pressure|target |stay |skip |serve with|garnish |removes |paste freezes|the |"
    r"whole coriander|comal|metate|salt when|soak |pressure |cook with|herbs and such)", re.I)


def num(s):
    s = s.strip()
    if s in FRAC:
        return FRAC[s]
    m = re.match(rf"^(\d+)\s+(\d+)/(\d+)$", s)
    if m:
        return int(m[1]) + int(m[2]) / int(m[3])
    m = re.match(rf"^(\d+)([{FR}])$", s)
    if m:
        return int(m[1]) + FRAC[m[2]]
    m = re.match(r"^(\d+)/(\d+)$", s)
    if m:
        return int(m[1]) / int(m[2])
    return float(s)


def r4(x):
    return None if x is None else round(x, 4)


def unit_of(u):
    return UNITS.get(u.lower()) if u else None


def parse_line(text, allow_qty=True):
    """'1¾ lb stewing beef (800 g), chuck' -> qty 1.75, unit lb, item 'stewing beef, chuck', alt 800 g."""
    out = {"text": text, "prefix": None, "qty": None, "qty_max": None, "unit": None, "item": text, "alt": None}
    if not allow_qty:
        return out
    m = QTY_RE.match(text)
    if not m:
        return out
    pre, q, q2, u, rest = m.groups()
    unit = unit_of(u)
    out.update(prefix=pre.strip().lower() if pre else None, qty=r4(num(q)), qty_max=r4(num(q2)) if q2 else None, unit=unit, item=rest.strip() or text)
    if unit:
        a = ALT_RE.search(rest)
        if a and "(" not in rest[:a.start()] and not re.search(rf"[\d{FR}]", rest[:a.start()]):
            au = unit_of(a[3])
            if au and ((unit in US) != (au in US)) and unit not in LENGTH and au not in LENGTH:
                out["alt"] = {"qty": r4(num(a[1])), "qty_max": r4(num(a[2])) if a[2] else None, "unit": au}
                keep = f" ({a[4].strip()})" if a[4] else ""
                out["item"] = (rest[:a.start()] + keep + rest[a.end():]).strip()
    return out


def kind_of(text, parsed, collection):
    if collection == "guides":
        return "note"
    t = text.strip()
    if t.startswith("["):
        return "note"
    if t.endswith(":"):
        return "label"
    if parsed["qty"] is not None:
        return "ingredient"
    if REF_RE.match(t):
        return "ref"
    if NOTE_RE.match(t) or ";" in t:
        return "note"
    return "ingredient"


def group_of(action):
    a = (action or "").lower()
    if a.startswith("options"):
        return "optional"
    if a.startswith("serve with"):
        return "serve"
    return "main"


def parse_items(items, collection, group, ingredients, step_no):
    out = []
    for it in items or []:
        text, sub = (it, []) if isinstance(it, str) else (it["text"], it.get("sub", []))
        p = parse_line(text, allow_qty=collection != "guides")
        p["kind"] = kind_of(text, p, collection)
        if p["kind"] not in ("ingredient",):
            p.update(prefix=None, qty=None, qty_max=None, unit=None, alt=None, item=text)
        if p["kind"] == "label" and sub:
            # "Chiles, a few seconds each:" with the chiles as sub-items: those are ingredients
            p["sub"] = parse_items(sub, collection, group, ingredients, step_no)
        else:
            p["sub"] = [{"text": s, "kind": "note"} for s in (sub or [])]
        if p["kind"] == "ingredient":
            ingredients.append({k: p[k] for k in ("prefix", "qty", "qty_max", "unit", "item", "alt")} | {"group": group, "step": step_no})
        out.append(p)
    return out


def parse_makes(makes):
    if not makes:
        return None
    m = re.match(rf"^(?:about\s+)?({NUM})(?:\s*(?:to|-|–)\s*({NUM}))?\s*(.*)$", makes.strip(), re.I)
    if not m:
        return {"text": makes, "qty": None, "qty_max": None, "label": makes}
    return {"text": makes, "qty": r4(num(m[1])), "qty_max": r4(num(m[2])) if m[2] else None, "label": m[3].strip()}


def build_recipe(src, rid):
    col = src["collection"]
    ingredients, steps = [], []
    for n, st in enumerate(src.get("steps", []), 1):
        if "table" in st:
            blocks = []
            for b in st["table"]:
                g = b.get("title") or "main"
                blocks.append({"title": b.get("title"), "url": b.get("url"), "action": b.get("action"),
                               "items": parse_items(b.get("items"), col, g, ingredients, n)})
            steps.append({"type": "table", "blocks": blocks})
        elif "text" in st:
            steps.append({"type": "text", "text": st["text"]})
        else:
            g = group_of(st.get("action"))
            steps.append({"type": "action", "text": st.get("action", ""), "group": g,
                          "items": parse_items(st.get("items"), col, g, ingredients, n)})
    tags = {k: list(src.get("tags", {}).get(k, [])) for k in TAG_KEYS}
    return {
        "id": rid, "title": src["title"], "collection": col, "section": src.get("section"),
        "source": src.get("source"), "makes": parse_makes(src.get("makes")), "added": src.get("added"),
        "origin": src.get("origin"), "description": src.get("description"), "beans": src.get("beans"),
        "tags": tags, "prep_min": src.get("prep_min"), "cook_min": src.get("cook_min"),
        "ingredients": ingredients, "steps": steps,
        "notes": src.get("notes", []), "editor_notes": src.get("edits", []),
    }


def validate(src, path):
    errs = []
    for k in ("title", "collection", "steps"):
        if k not in src:
            errs.append(f"missing '{k}'")
    if src.get("added") and not re.match(r"^\d{4}-\d{2}-\d{2}$", src["added"]):
        errs.append("'added' must be YYYY-MM-DD")
    for k in src.get("tags", {}):
        if k not in TAG_KEYS:
            errs.append(f"unknown tag group '{k}'")
    for st in src.get("steps", []):
        if not ({"action", "items"} & st.keys() or "text" in st or "table" in st):
            errs.append(f"bad step {st!r:.60}")
    return [f"{os.path.relpath(path, ROOT)}: {e}" for e in errs]


def cmd_build(args):
    cols = json.load(open(COLLECTIONS, encoding="utf-8"))
    order = {c["id"]: i for i, c in enumerate(cols)}
    recipes, errs, ids = [], [], set()
    for path in sorted(glob.glob(os.path.join(SRC_DIR, "*", "*.json"))):
        src = json.load(open(path, encoding="utf-8"))
        rid = os.path.splitext(os.path.basename(path))[0]
        e = validate(src, path)
        if src.get("collection") not in order:
            e.append(f"{os.path.relpath(path, ROOT)}: collection '{src.get('collection')}' not in collections.json")
        if os.path.basename(os.path.dirname(path)) != src.get("collection"):
            e.append(f"{os.path.relpath(path, ROOT)}: folder does not match collection")
        if rid in ids:
            e.append(f"duplicate id {rid}")
        ids.add(rid)
        errs += e
        if not e and not src.get("hidden"):
            recipes.append((src.get("sort", 9999), build_recipe(src, rid)))
    if errs:
        sys.exit("Build failed:\n  " + "\n  ".join(errs))
    recipes = [r for _, r in sorted(recipes, key=lambda x: (order[x[1]["collection"]], x[0], x[1]["title"]))]
    n_rec = sum(r["collection"] != "guides" for r in recipes)
    data = {"built": date.today().isoformat(), "count": n_rec, "collections": cols, "recipes": recipes}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    by = {}
    for r in recipes:
        by[r["collection"]] = by.get(r["collection"], 0) + 1
    print(f"Wrote {os.path.relpath(OUT, ROOT)}: {n_rec} recipes, {len(recipes) - n_rec} guides")
    for c in cols:
        print(f"  {c['id']:8} {by.get(c['id'], 0)}")
    unparsed = sum(1 for r in recipes for i in r["ingredients"] if i["qty"] is None)
    print(f"  ingredient lines: {sum(len(r['ingredients']) for r in recipes)} ({unparsed} without a quantity)")
    if args.expect is not None and n_rec != args.expect:
        sys.exit(f"Expected {args.expect} recipes, got {n_rec}")


# ---------------------------------------------------------------- import from the Drive archive
def slugify(s):
    s = unicodedata.normalize("NFKD", s.split(" (")[0] or s)
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:60] or "recipe"


def conv_items(items):
    out = []
    for it in items or []:
        if isinstance(it, str):
            out.append(it)
        else:
            out.append({"text": it["t"], "sub": [s if isinstance(s, str) else s["t"] for s in it.get("sub", [])]})
    return out


def conv_steps(steps):
    out = []
    for st in steps:
        if "table" in st:
            out.append({"table": [{"title": b.get("title"), "url": b.get("url"), "action": b.get("a"),
                                   "items": conv_items(b.get("i"))} for b in st["table"]]})
        elif "p" in st:
            out.append({"text": st["p"]})
        else:
            out.append({"action": st.get("a", ""), "items": conv_items(st.get("i"))})
    return out


KEEP = ("tags", "prep_min", "cook_min", "hidden")


def cmd_import(args):
    from autotag import default_tags  # initial tags for recipes that have none yet
    existing = {}
    for path in glob.glob(os.path.join(SRC_DIR, "*", "*.json")):
        s = json.load(open(path, encoding="utf-8"))
        existing[(s["collection"], s["title"])] = (path, s)
    written, used = 0, set()

    def emit(col, section, r, sort, title=None):
        nonlocal written
        title = title or r["t"]
        path, old = existing.get((col, title), (None, None))
        rid = os.path.splitext(os.path.basename(path))[0] if path else slugify(title)
        base, n = rid, 2
        while (col, rid) in used:
            rid, n = f"{base}-{n}", n + 1
        used.add((col, rid))
        src = {"title": title, "collection": col, "section": section, "sort": sort,
               "source": r.get("src"), "makes": r.get("makes"), "added": r.get("added"),
               "origin": r.get("from"), "description": r.get("desc"), "beans": r.get("beans"),
               "tags": None, "prep_min": None, "cook_min": None,
               "steps": conv_steps(r.get("steps", [])), "notes": r.get("notes", []), "edits": r.get("edits", [])}
        if old:
            for k in KEEP:
                if k in old:
                    src[k] = old[k]
        if not src["tags"]:
            src["tags"] = default_tags(src)
        src = {k: v for k, v in src.items() if v is not None or k in ("prep_min", "cook_min")}
        d = os.path.join(SRC_DIR, col)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, rid + ".json"), "w", encoding="utf-8") as f:
            json.dump(src, f, ensure_ascii=False, indent=1)
            f.write("\n")
        written += 1

    for col, fn in (("house", args.house), ("raza", args.raza), ("beans", args.beans)):
        if not fn:
            continue
        d = json.load(open(fn, encoding="utf-8"))
        sort = 0
        for f in d.get("fundamentals", []):
            sort += 1
            emit("guides", "Bean Basics", f, sort, title=f["h"])
        for s in d["sections"]:
            for r in s["recipes"]:
                sort += 1
                emit(col, s["title"], r, sort)
        if col == "raza":
            cols = json.load(open(COLLECTIONS, encoding="utf-8"))
            for c in cols:
                if c["id"] == "raza":
                    c["conventions"] = d.get("conventions", [])
            with open(COLLECTIONS, "w", encoding="utf-8") as f:
                json.dump(cols, f, ensure_ascii=False, indent=1)
                f.write("\n")
    print(f"Wrote {written} source files under recipes/. Now run: python3 -I build.py build")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    b = sub.add_parser("build")
    b.add_argument("--expect", type=int)
    i = sub.add_parser("import")
    i.add_argument("--house")
    i.add_argument("--raza")
    i.add_argument("--beans")
    a = ap.parse_args()
    if a.cmd == "import":
        sys.path.insert(0, ROOT)
        cmd_import(a)
    else:
        if a.cmd is None:
            a.expect = None
        cmd_build(a)


if __name__ == "__main__":
    main()
