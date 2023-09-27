from pathlib import Path
from inspect import cleandoc as dedent
import httpx
import yaml


# Fetch themes from MkDocs catalog.
catalog = yaml.safe_load(httpx.get("https://raw.githubusercontent.com/mkdocs/catalog/main/projects.yaml").text)
projects = catalog["projects"]
theming_category = [project for project in projects if project["category"] == "theming"]
themes = []
for project in theming_category:
    if mkdocs_theme := project.get("mkdocs_theme"):
        if isinstance(mkdocs_theme, str):
            themes.append((project["name"], mkdocs_theme))
        else:
            for theme in mkdocs_theme:
                themes.append((f"{project['name']} - {theme.title()}", theme))
themes = sorted(themes, key=lambda theme: theme[0].lower())


# Pre-build list of themes in navigation.
conf_nav_themes = "\n".join(f"  - {name}: ../{theme}" for name, theme in themes)


# MkDocs configuration for each theme.
theme_conf = """site_name: {site_name}
theme: {theme}
nav:
- Gallery: ../../
- Themes:
""" + conf_nav_themes


# Prepare each theme (docs directory and configuration file).
for name, theme in themes:
    theme_dir = Path("themes", theme)
    theme_dir.mkdir(parents=True, exist_ok=True)
    demo_docs_dir = Path("demo").absolute()
    docs_dir = theme_dir / "docs"
    if not docs_dir.exists():
        docs_dir.symlink_to(demo_docs_dir, target_is_directory=True)
    with theme_dir.joinpath("mkdocs.yml").open("w") as conf_file:
        print(theme_conf.format(site_name=name, theme=theme), file=conf_file)


# Our main MkDocs configuration.
main_conf = f"""site_name: Gallery
theme:
  name: material
  features:
  - navigation.sections
"""

with open("mkdocs.yml", "w") as conf_file:
    print(main_conf, file=conf_file)


# The home page.
index_contents = """---
hide:
- navigation
---

# Welcome to our gallery of MkDocs themes

<style>
img {
    -webkit-filter: drop-shadow(0px 16px 10px rgba(100,100,100,0.6));
    -moz-filter: drop-shadow(0px 16px 10px rgba(100,100,100,0.6));
    -ms-filter: drop-shadow(0px 16px 10px rgba(100,100,100,0.6)); 
    -o-filter: drop-shadow(0px 16px 10px rgba(100,100,100,0.6));
    filter: drop-shadow(0px 16px 10px rgba(100,100,100,0.6));
}
</style>
"""

Path("docs").mkdir(parents=True, exist_ok=True)
with open("docs/index.md", "w") as index_page:
    print(index_contents, file=index_page)
    for name, theme in themes:
        img = f"![{name}](../../img/{theme}.png)"
        link = f"[{img}](themes/{theme})"
        print(f"## {name}\n\n{link}\n\n---\n\n", file=index_page)
