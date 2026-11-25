# Working on banksbean/recipes

- This repo is the master copy of Ryan's recipes and the only website (recipes.beansalad.org, GitHub Pages from `main`).
  Do not use the Google Drive archive, `data.js`, `build.py import`, or the Mac for recipe work. None of it is needed.
- New recipe (photo, link, text, or "write me one"): convert it to the Recipe Writing Standard (in the claude.ai
  "Food and Recipes" project, and summarized in README "Source file format"), then follow README "Adding a recipe".
  Beans go to `beans`, everything else to `house`, unless Ryan says otherwise.
- Always: `python3 -I build.py build --expect N`, preview the recipe in a narrow window (screenshot), commit, and
  `git -c push.negotiate=true push origin main`. The build also regenerates `exports/*.docx`; commit those too.
- Never hand-edit `data/recipes.json` or `exports/`. Never upload HTML from the Drive folder.
- Site design lives in `index.html`. Headings use DM Sans; palette comes from the BeanSalad.org logo.
- Commit messages: short summary line naming the recipe or change.
