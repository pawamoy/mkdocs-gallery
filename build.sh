#!/usr/bin/env bash

echo "Preparing environments"
for theme in themes/*; do
    (
        cd "${theme}"
        if [ ! -d .venv ]; then
            python -m venv .venv
            .venv/bin/pip install $(mkdocs get-deps) &>/dev/null
        fi
    ) &
done

wait

rm -rf site
mkdir -p logs docs/img site/themes &>/dev/null

for theme in themes/*; do
    echo "Building ${theme}"
    (
        cd "${theme}"
        if .venv/bin/mkdocs build &>../../logs/${theme##*/}.txt; then
            mv site "../../site/themes/${theme##*/}"
        else
            echo "FAILED!"
        fi
    )
done

echo "Taking screenshots"
for theme in site/themes/*; do
    shot-scraper --wait 1000 "${theme}/index.html" -o "docs/img/${theme##*/}.png"
done

echo "Building main documentation"
mkdocs build --dirty
