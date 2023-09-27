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

echo "Building main documentation"
rm -rf site
mkdocs build
mkdir site/themes
mkdir logs &>/dev/null

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
