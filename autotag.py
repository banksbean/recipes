"""Initial tags for recipes imported without any (used by `build.py import`).

These are starting guesses, written once into each source file. After that the
source file's "tags" are the truth: edit them there, and import will keep them.
"""
import re

CUISINE_BY_TITLE = [
    (r"lion's head|红烧", ["Chinese"]),
    (r"cochinita", ["Mexican"]),
    (r"texas-style chili", ["Tex-Mex"]),
    (r"chile colorado|rajas|pickled red onions|charro|chiapas", ["Mexican"]),
    (r"prik shew", ["Thai"]),
    (r"sangria", ["Spanish"]),
    (r"red beans and rice", ["Cajun & Creole"]),
    (r"tomatillo bean chili|chili sin carne|santa maria", ["Southwestern"]),
    (r"tamarind greens|beans and apricots|preserved lemon, chile", ["Middle Eastern"]),
    (r"adzuki bean miso", ["Japanese"]),
    (r"italian red bean|tuscan|pasta with cicerchia", ["Italian"]),
    (r"habichuelas", ["Puerto Rican"]),
    (r"lemongrass and coconut", ["Southeast Asian"]),
    (r"loubia", ["Moroccan"]),
    (r"cassoulet", ["French"]),
    (r"porotos granados", ["Chilean"]),
    (r"fish and shrimp stew", ["Spanish"]),
    (r"garbanzo salad", ["Mediterranean"]),
    (r"lentil salad", ["French"]),
]
COLLECTION_CUISINE = {"raza": ["Pakistani & North Indian"]}
SECTION_CUISINE = {"Casa Crespo (Oaxaca)": ["Mexican"]}

COURSE_BY_SECTION = {
    "Mains": ["Main"], "Soups & Stews": ["Soup & Stew"], "Sides": ["Side"],
    "Salsas & Condiments": ["Condiment"], "Drinks": ["Drink"], "Desserts": ["Dessert"],
    "Basics": ["Basic"], "Beef": ["Main"], "Chicken": ["Main"], "Seafood": ["Main"],
    "Vegetables": ["Side"], "Daal (Lentils)": ["Main"], "Rice": ["Side"], "Soups": ["Soup & Stew"],
    "Chutneys & Accompaniments": ["Condiment"], "Single Pot": ["Main"], "Stovetop & Oven": ["Main"],
    "Cold": ["Salad"],
}
COURSE_BY_TITLE = [
    (r"^mole|tacos al pastor|tamales", ["Main"]), (r"caldo", ["Soup & Stew"]),
    (r"salsa|guacamole", ["Condiment"]), (r"nixtamal|tortillas", ["Basic"]), (r"helado", ["Dessert"]),
    (r"soup", ["Soup & Stew"]), (r"chili|stew", ["Soup & Stew"]), (r"burgers", ["Main"]),
    (r"basic cooked beans|verified white beans", ["Side"]),
]

PROTEIN = [  # (label, pattern searched in ingredient text)
    ("Seafood", r"\b(shrimp|fish|prawns?)\b"),
    ("Poultry", r"\b(chicken|turkey)\b"),
    ("Beef", r"\b(beef|sirloin|chuck|suet)\b"),
    ("Pork", r"\b(pork|bacon|ham|sausages?|'nduja|lard|chicharr[oó]n)\b"),
    ("Beans & Lentils", r"\b(beans?|lentils?|daal|garbanzos?|chickpeas?|chholay)\b"),
    ("Egg", r"\beggs?\b"),
]
MEATLESS_OK = {"Beans & Lentils", "Egg"}
PROTEIN_OVERRIDE = {  # title prefix -> protein tags, where the keyword scan gets it wrong
    "Guacamole": ["Vegetarian"], "Helado de Elote": ["Vegetarian"], "Tamales de Flor": ["Cheese"],
    "Simple Pulao": [], "Khatti Meethi Binis": ["Vegetarian"], "Chholay": ["Beans & Lentils", "Vegetarian"],
}

SEASON_BY_TITLE = [
    (r"helado|sangria|salad|guacamole|salsa verde|kachumar|raita|mango", ["Summer"]),
    (r"chili|stew|caldo|cassoulet|soup|gratin|casserole|halwa|tamales|mole|loubia|porotos", ["Fall", "Winter"]),
]


def _texts(src):
    out = []
    for st in src.get("steps", []):
        blocks = st.get("table") or [st]
        for b in blocks:
            if re.match(r"(serve with|options)", b.get("action") or "", re.I):
                continue
            for it in b.get("items") or []:
                out.append(it if isinstance(it, str) else it["text"])
    return " | ".join(out).lower()


def _first(rules, s):
    for pat, val in rules:
        if re.search(pat, s, re.I):
            return list(val)
    return None


def default_tags(src):
    if src["collection"] == "guides":
        return {"cuisine": [], "course": ["Guide"], "protein": [], "season": []}
    title = src["title"]
    cuisine = (_first(CUISINE_BY_TITLE, title) or COLLECTION_CUISINE.get(src["collection"])
               or SECTION_CUISINE.get(src.get("section")) or ["American"])
    course = _first(COURSE_BY_TITLE, title) if src["collection"] != "raza" else None
    course = course or COURSE_BY_SECTION.get(src.get("section"), ["Main"])
    text = _texts(src)
    if src["collection"] == "beans":
        text += " | beans"
    text = re.sub(r"fish sauce|(chicken|beef|vegetable) (stock|broth)|bouillon|shrimp paste", "", text)
    protein = [lab for lab, pat in PROTEIN if re.search(pat, text)]
    if "Egg" in protein and len(protein) > 1:
        protein.remove("Egg")  # eggs as a binder are not the protein
    if src.get("section") == "Drinks":
        protein = []
    elif not set(protein) - MEATLESS_OK:
        protein.append("Vegetarian")
    for k, v in PROTEIN_OVERRIDE.items():
        if title.startswith(k):
            protein = list(v)
    season = _first(SEASON_BY_TITLE, title) or ["Any"]
    return {"cuisine": cuisine, "course": course, "protein": protein, "season": season}
