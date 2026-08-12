# Intentionally empty, and intentionally NOT deleted. Nothing imports `app.text` — this folder
# holds only .md and .json documents — but `[tool.setuptools.packages.find]` discovers packages BY
# the presence of this file. Without it the folder is not a package, so the documents drop out of
# the installed distribution and the loaders raise FileNotFoundError mid-run.
#
# Verified, not assumed: `find_packages(where="api")` lists `app.text` only while this file
# exists. Today both environments happen to forgive its absence — an editable install points at
# the working tree, and the image runs `COPY app/ ./app/` — which is exactly why removing it would
# break somewhere else (a wheel, a plain `pip install .`) rather than here.
#
# WHAT LIVES HERE — two regimes that look alike and are not (see CLAUDE.md -> "Prompty"):
#   * OURS, git-only, guard-tested: prompt_parse_ticket_user.md and
#     prompt_parse_ticket_system.md. Editing them changes the meaning of every FUTURE artifact
#     in data/parsed/ (rule 7), so they are never exposed to the customer nor edited at runtime.
#   * CUSTOMER DATA, versioned by a field inside the file: dict_resolution.json. Stage 8 moves
#     it to the SQL rules store, where it becomes editable through a GUI.
# The folder is flat, so the distinction is NOT visible in the path — each file states its own
# regime in its header, and that header is the only thing keeping them apart.
