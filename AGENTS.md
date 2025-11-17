# Assassyn

Assassyn is a project on next-generation hardware agile design and implementation by providing
a unified interface for both simulation and RTL generation.

## Development Guideline

- To run anything within this repo:
  - run `ass` to set up the environment. This project depends on several complicated environment variables.
  - If you could run it directly in interactive shell, ignore the below notes; Otherwise, the ass helper is defined as a zsh alias that sets up Assassyn’s environment; non-interactive shells cannot load it. I invoked all simulator/test commands as zsh -ic "ass >/dev/null && <command>", which sources the alias before running Python. The noisy oh-my-zsh/gitstatus warnings originate from running zsh non-interactively but do not affect the setup.

