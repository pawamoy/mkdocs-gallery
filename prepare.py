from pathlib import Path
from inspect import cleandoc as dedent
from dataclasses import dataclass
from jinja2 import Environment

import httpx
import yaml
import shutil

jinja = Environment(autoescape=False)

@dataclass
class Theme:
    name: str
    mkdocs_id: str
    url: str = ""
    pypi_id: str = ""


# Fetch themes from MkDocs catalog.
catalog = yaml.safe_load(httpx.get("https://raw.githubusercontent.com/mkdocs/catalog/main/projects.yaml").text)
projects = catalog["projects"]
theming_category = [project for project in projects if project["category"] == "theming"]
themes = []
for project in theming_category:
    if mkdocs_theme := project.get("mkdocs_theme"):
        if "github_id" in project:
            url = f"https://github.com/{project['github_id']}"
        elif "gitlab_id" in project:
            url = f"https://gitlab.com/{project['gitlab_id']}"
        else:
            url = ""
        pypi_id = project.get("pypi_id", f"git+{url}")
        if isinstance(mkdocs_theme, str):
            themes.append(Theme(name=project["name"], url=url, pypi_id=pypi_id, mkdocs_id=mkdocs_theme))
        else:
            for theme in mkdocs_theme:
                themes.append(Theme(name=f"{project['name']} - {theme.title()}", url=url, pypi_id=pypi_id, mkdocs_id=theme))
themes = sorted(themes, key=lambda theme: theme.name.lower())
builtin_themes = [
    Theme(name="MkDocs", mkdocs_id="mkdocs"),
    Theme(name="ReadTheDocs", mkdocs_id="readthedocs"),
]


# Prepare each theme (docs directory and configuration file).
specimen_dir = Path("specimen").absolute()
for theme in builtin_themes + themes:
    # Copy specific directory, or default to specimen.
    theme_dir = Path("themes", theme.mkdocs_id)
    theme_conf_dir = Path("themes_conf", theme.mkdocs_id)
    if not theme_conf_dir.exists():
        theme_conf_dir = specimen_dir
    shutil.copytree(theme_conf_dir, theme_dir, dirs_exist_ok=True)

    # Update mkdocs.yml.
    mkdocs_yml = theme_dir / "mkdocs.yml"
    mkdocs_yml.write_text(jinja.from_string(mkdocs_yml.read_text()).render(theme=theme.mkdocs_id, site_name=theme.name, themes=themes))

    # Update docs/index.md.
    index_md = theme_dir / "docs" / "index.md"
    index_md.write_text(jinja.from_string(index_md.read_text()).render(theme=theme, themes=themes))


# Our main MkDocs configuration.
main_conf = f"""site_name: Gallery
site_url: https://pawamoy.github.io/mkdocs-gallery
theme:
  name: material
  logo: assets/logo.png
  palette:
  - media: "(prefers-color-scheme: light)"
    scheme: default
    primary: blue
    toggle:
      icon: material/brightness-7 
      name: Switch to dark mode
  - media: "(prefers-color-scheme: dark)"
    scheme: slate
    primary: blue
    toggle:
      icon: material/brightness-4
      name: Switch to light mode
markdown_extensions:
- attr_list
- toc:
    permalink: true
"""

Path("mkdocs.yml").write_text(main_conf)


# The home page.
index_contents = """---
hide:
- navigation
---

# Welcome to our gallery of MkDocs themes!

<style>
article img {
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
    print("## Built-in themes\n", file=index_page)
    for theme in builtin_themes:
        img = f"![{theme.name}](assets/img/{theme.mkdocs_id}.png)"
        link = f"[{img}](themes/{theme.mkdocs_id}){{ title=\"Click to browse!\" }}"
        print(f"### {theme.name}\n\n{link}\n\n---\n\n", file=index_page)
    print("## Third-party themes\n", file=index_page)
    for theme in themes:
        img = f"![{theme.name}](assets/img/{theme.mkdocs_id}.png)"
        link = f"[{img}](themes/{theme.mkdocs_id}){{ title=\"Click to browse!\" }}"
        print(f"### {theme.name}\n\n{link}\n\n---\n\n", file=index_page)
