import argparse
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from multiprocessing import Pool
from pathlib import Path

import httpx
import yaml
from jinja2 import Environment
from shot_scraper.cli import cli as shot_scraper
from tqdm import tqdm
import mkdocs_get_deps


@dataclass
class Theme:
    name: str
    mkdocs_id: str
    url: str = ""
    pypi_id: str = ""
    builtin: bool = False


_builtin_themes = [
    Theme(name="MkDocs", mkdocs_id="mkdocs", builtin=True),
    Theme(name="ReadTheDocs", mkdocs_id="readthedocs", builtin=True),
]


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
                themes.append(Theme(name=project["name"], url=url, pypi_id=pypi_id, mkdocs_id=mkdocs_theme))
            else:
                for theme in mkdocs_theme:
                    themes.append(
                        Theme(name=f"{project['name']} - {theme.title()}", url=url, pypi_id=pypi_id, mkdocs_id=theme)
                    )
    return _builtin_themes + sorted(themes, key=lambda theme: theme.name.lower())


# Copy files and expand Jinja templates.
def _prepare_site(src_dir: Path, dest_dir: Path, themes: list[Theme], theme: Theme | None = None) -> None:
    jinja = Environment(autoescape=False)
    dest_dir.mkdir(parents=True, exist_ok=True)

    for src_path in src_dir.rglob("*"):
        if not src_path.is_file():
            continue
        dest_path = dest_dir.joinpath(src_path.relative_to(src_dir))
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        if src_path.suffix in (".md", ".yml"):
            content = src_path.read_text()
            content = jinja.from_string(content).render(themes=themes, theme=theme)
            dest_path.write_text(content)
        else:
            shutil.copyfile(src_path, dest_path)


# Prepare each theme (docs directory and configuration file).
def prepare_themes(themes: list[Theme]) -> None:
    specimen_dir = Path("templates", "specimen")
    for theme in themes:
        # Copy specific directory, or default to specimen.
        theme_dir = Path("themes", theme.mkdocs_id)
        theme_conf_dir = Path("templates", "themes", theme.mkdocs_id)
        if not theme_conf_dir.exists():
            theme_conf_dir = specimen_dir
        shutil.copytree(theme_conf_dir, theme_dir, dirs_exist_ok=True)

        _prepare_site(specimen_dir, theme_dir, themes, theme=theme)


# Prepare the main documentation site.
def prepare_main(themes: list[Theme]) -> None:
    _prepare_site(Path("templates", "main"), Path("."), themes)


# Create virtualenvs and install dependencies.
def install_deps(theme: Theme) -> None:
    # print(f"Installing dependencies for {theme.mkdocs_id}")
    theme_dir = Path("themes", theme.mkdocs_id)
    venv_dir = theme_dir / ".venv"
    if not venv_dir.exists():
        subprocess.run(
            [sys.executable, "-muv", "venv", "--seed", venv_dir],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    deps = mkdocs_get_deps.get_deps(config_file=theme_dir / "mkdocs.yml")
    subprocess.run(
        [venv_dir / "bin" / "pip", "install", "uv"],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    subprocess.run(
        [venv_dir / "bin" / "uv", "pip", "install", *deps],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env={"VIRTUAL_ENV": str(venv_dir), "UV_PROJECT_ENVIRONMENT": str(venv_dir)},
    )



def _build_theme(theme: Theme) -> None:
    theme_dir = Path("themes", theme.mkdocs_id).absolute()
    dest_dir = Path("site", "themes", theme.mkdocs_id).absolute()
    print(f"Building {theme.name}")
    with logs_dir.joinpath(f"{theme.mkdocs_id}.txt").open("w") as logs_file:
        try:
            subprocess.run(
                [theme_dir.joinpath(".venv", "bin", "mkdocs"), "build", "-d", dest_dir],
                stdout=logs_file,
                stderr=logs_file,
                check=True,
                text=True,
                cwd=theme_dir,
            )
        except subprocess.CalledProcessError:
            print("FAILED!")


def _take_screenshot(theme: Theme) -> None:
    try:
        shot_scraper(
            [f"site/themes/{theme.mkdocs_id}/index.html", "-o", f"docs/assets/img/{theme.mkdocs_id}.png"]
        )
    except Exception as error:
        print(error)
    except BaseException:
        pass


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
        shutil.rmtree(Path("site", "themes"), ignore_errors=True)
        Path("site", "themes").mkdir(parents=True)
        with Pool(len(os.sched_getaffinity(0))) as pool:
            tuple(pool.imap(_build_theme, themes))

    if not opts.take_screenshots:
        print("Skipping screenshots")
    else:
        print("Taking screenshots")
        Path("docs", "assets", "img").mkdir(parents=True, exist_ok=True)

        with Pool(len(os.sched_getaffinity(0))) as pool:
            tuple(pool.imap(_take_screenshot, themes))


# Build main documentation site.
def build_main() -> None:
    print("Building gallery's main site")
    subprocess.run([sys.executable, "-mmkdocs", "build", "--dirty"], check=True)


logs_dir = Path("logs")

# Run everything.
def main() -> None:
    logs_dir.mkdir(exist_ok=True)
    themes = get_themes()
    prepare_themes(themes)
    prepare_main(themes)
    build_themes(themes)
    build_main()


if __name__ == "__main__":
    main()
