#!/usr/bin/env bash

NO_DEPS=0
NO_THEMES=0
NO_SHOTS=0

while [ $# -ne 0 ]; do
    case $1 in
        -D|--no-deps) NO_DEPS=1 ;;
        -T|--no-themes) NO_THEMES=1 ;;
        -S|--no-shots) NO_SHOTS=1 ;;
    esac
    shift
done

if [ ${NO_DEPS} -eq 1 ]; then
    echo "Skipping dependencies installation"
else
    echo "Preparing environments"
    for theme in themes/*; do
        (
            cd "${theme}"
            if [ ! -d .venv ]; then
                python -m venv .venv
            fi
            .venv/bin/pip install $(mkdocs get-deps) &>/dev/null
        ) &
    done
fi

wait

if [ ${NO_THEMES} -eq 1 ]; then
    echo "Skipping themes building"
else
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
fi

if [ ${NO_SHOTS} -eq 1 ]; then
    echo "Skipping screenshots"
else
    echo "Taking screenshots"
    for theme in site/themes/*; do
        shot-scraper "${theme}/index.html" -o "docs/assets/img/${theme##*/}.png"
    done
fi

echo "Building main documentation"
mkdocs build --dirty
