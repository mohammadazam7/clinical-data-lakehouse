# Contributing

## Set up

```bash
python -m venv .venv && source .venv/bin/activate
make install
pre-commit install
```

## Branches and commits

- Branch from `main` with a short, descriptive name: `feat/<topic>`, `fix/<topic>`,
  `docs/<topic>` or `chore/<topic>`. Milestone branches use `m<N>-<topic>`.
- One logical change per commit. Subject line in the imperative mood, under 72
  characters; a body that explains why when the change is not obvious.
- Commits are signed. Never commit credentials, generated data or files under `data/`.

## Before opening a pull request

```bash
make check          # ruff, ruff format, mypy (strict) and pytest
```

Pull requests follow the template: summary, motivation, changes, testing and
follow-ups. A change to a mapping must come with a test that pins the source code and
the OMOP concept it maps to. Never add real patient data, even de-identified, to an
issue, a test or a fixture. Main is merged with a merge commit once CI passes.

## Releases

Each completed milestone is tagged `v0.N.0`; the first complete release is `v1.0.0`.
`CHANGELOG.md` follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
