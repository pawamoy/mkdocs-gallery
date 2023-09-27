#!/usr/bin/env bash

rm -rf site
mkdocs build
mkdir -p site/themes

mkdir logs &>/dev/null
for theme in themes/*; do
    if (
        cd "${theme}"
        if [ ! -d .venv ]; then
            echo "Preparing environment for ${theme}"
            python -m venv .venv
            .venv/bin/pip install mkdocs &>/dev/null
            .venv/bin/pip install $(mkdocs get-deps) &>/dev/null
        fi
        echo "Building ${theme}"
        .venv/bin/mkdocs build &>../../logs/${theme##*/}.txt
    ); then
        mv "${theme}/site" "site/themes/${theme##*/}"
    else
        echo "FAILED!"
    fi
done
