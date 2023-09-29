import argparse
import os
import shutil
import subprocess
import sys
import venv
from dataclasses import dataclass
from multiprocessing import Pool
from pathlib import Path
from textwrap import dedent

import httpx
import yaml
from jinja2 import Environment
from mkdocs.commands.build import build as mkdocs_build
from mkdocs.config import load_config
from shot_scraper.cli import cli as shot_scraper
from tqdm import tqdm


@dataclass
class Theme:
    name: str
    mkdocs_id: str
    url: str = ""
    pypi_id: str = ""


builtin_themes = [
    Theme(name="MkDocs", mkdocs_id="mkdocs"),
    Theme(name="ReadTheDocs", mkdocs_id="readthedocs"),
]

# TODO: These themes need fixing or maybe removal from the catalog.
broken_themes = {
    "docskimmer",
    "inspired",
    "jinks_en",
    "lantana",
    "semantic",
    "unidata",
}


# Fetch themes from MkDocs catalog.
def get_themes() -> list[Theme]:
    # TODO: Replace with local path when merging within catalog.
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
                if mkdocs_theme in broken_themes:
                    continue
                themes.append(Theme(name=project["name"], url=url, pypi_id=pypi_id, mkdocs_id=mkdocs_theme))
            else:
                for theme in mkdocs_theme:
                    if theme in broken_themes:
                        continue
                    themes.append(
                        Theme(name=f"{project['name']} - {theme.title()}", url=url, pypi_id=pypi_id, mkdocs_id=theme)
                    )
    return sorted(themes, key=lambda theme: theme.name.lower())


# Prepare each theme (docs directory and configuration file).
def prepare_themes(themes: list[Theme]) -> None:
    jinja = Environment(autoescape=False)
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
        mkdocs_yml.write_text(
            jinja.from_string(mkdocs_yml.read_text()).render(theme=theme.mkdocs_id, site_name=theme.name, themes=themes)
        )

        # Update docs/index.md.
        index_md = theme_dir / "docs" / "index.md"
        index_md.write_text(jinja.from_string(index_md.read_text()).render(theme=theme, themes=themes))


# Prepare the main documentation site.
def prepare_main(themes: list[Theme]) -> None:
    # Our main MkDocs configuration.
    main_conf = dedent(
        """
        site_name: Gallery
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
    ).strip()

    Path("mkdocs.yml").write_text(main_conf)

    # The home page.
    index_contents = dedent(
        """
        ---
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
    ).strip()

    Path("docs").mkdir(parents=True, exist_ok=True)
    with open("docs/index.md", "w") as index_page:
        print(index_contents, file=index_page)
        print("\n## Built-in themes\n", file=index_page)
        for theme in builtin_themes:
            img = f"![{theme.name}](assets/img/{theme.mkdocs_id}.png)"
            link = f'[{img}](themes/{theme.mkdocs_id}){{ title="Click to browse!" }}'
            print(f"### {theme.name}\n\n{link}\n\n---\n\n", file=index_page)
        print("\n## Third-party themes\n", file=index_page)
        for theme in themes:
            img = f"![{theme.name}](assets/img/{theme.mkdocs_id}.png)"
            link = f'[{img}](themes/{theme.mkdocs_id}){{ title="Click to browse!" }}'
            print(f"### {theme.name}\n\n{link}\n\n---\n\n", file=index_page)


# Create virtualenvs and install dependencies.
def install_deps(theme: Theme) -> None:
    # print(f"Installing dependencies for {theme.mkdocs_id}")
    theme_dir = Path("themes", theme.mkdocs_id)
    venv_dir = theme_dir / ".venv"
    if not venv_dir.exists():
        venv.create(venv_dir, with_pip=True)
    # NOTE: If `get_deps` returns a list at some point, we could use this instead of a subprocess:
    # deps = get_deps(
    #     projects_file_url="https://raw.githubusercontent.com/mkdocs/catalog/main/projects.yaml",
    #     config_file_path=theme_dir / "mkdocs.yml"
    # )
    with open(os.devnull, "w") as devnull:
        deps = (
            subprocess.run(
                [sys.executable, "-mmkdocs", "get-deps", "-f", theme_dir / "mkdocs.yml"],
                check=False,
                stdout=subprocess.PIPE,
                stderr=devnull,
                text=True,
            )
            .stdout.strip()
            .split("\n")
        )
        subprocess.run([venv_dir / "bin" / "pip", "install", *deps], check=False, stdout=devnull, stderr=devnull)


# Build theme sites.
def build_themes(themes: list[Theme]) -> None:
    parser = argparse.ArgumentParser(prog="build.py")
    parser.add_argument(
        "-D",
        "--no-deps",
        dest="install_deps",
        action="store_false",
        default=True,
        help="Don't install Python dependencies.",
    )
    parser.add_argument(
        "-T",
        "--no-themes",
        dest="build_themes",
        action="store_false",
        default=True,
        help="Don't rebuild each theme site.",
    )
    parser.add_argument(
        "-S",
        "--no-shots",
        dest="take_screenshots",
        action="store_false",
        default=True,
        help="Don't take screenshots of each theme.",
    )

    opts = parser.parse_args()

    if not opts.install_deps:
        print("Skipping dependencies installation")
    else:
        print("Preparing environments")

        with Pool(len(os.sched_getaffinity(0))) as pool:
            tuple(tqdm(pool.imap(install_deps, themes), total=len(themes)))

    if not opts.build_themes:
        print("Skipping themes building")
    else:
        shutil.rmtree("site", ignore_errors=True)
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)
        Path("site", "themes").mkdir(parents=True, exist_ok=True)

        def _build_theme(theme: Theme) -> None:
            theme_dir = Path("themes", theme.mkdocs_id)
            print(f"Building {theme.name}")
            with logs_dir.joinpath(f"{theme.mkdocs_id}.txt").open("w") as logs_file:
                try:
                    subprocess.run(
                        [".venv/bin/mkdocs", "build"],
                        stdout=logs_file,
                        stderr=logs_file,
                        check=True,
                        text=True,
                        cwd=theme_dir,
                    )
                except subprocess.CalledProcessError:
                    print("FAILED!")
                else:
                    shutil.move(theme_dir / "site", f"site/themes/{theme.mkdocs_id}")

        for theme in themes:
            _build_theme(theme)

    if not opts.take_screenshots:
        print("Skipping screenshots")
    else:
        print("Taking screenshots")
        Path("docs", "assets", "img").mkdir(parents=True, exist_ok=True)
        for theme in themes:
            try:
                shot_scraper(
                    [f"site/themes/{theme.mkdocs_id}/index.html", "-o", f"docs/assets/img/{theme.mkdocs_id}.png"]
                )
            except:
                pass


# Build main documentation site.
def build_main() -> None:
    print("Building gallery's main site")
    mkdocs_config = load_config()
    mkdocs_config["plugins"].run_event("startup", command="build", dirty=False)
    try:
        mkdocs_build(mkdocs_config, dirty=True)
    finally:
        mkdocs_config["plugins"].run_event("shutdown")


# Run everything.
def main() -> None:
    themes = get_themes()
    prepare_themes(themes)
    prepare_main(themes)
    build_themes(builtin_themes + themes)
    build_main()


if __name__ == "__main__":
    main()
