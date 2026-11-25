# Settings compatibility fixtures

Each folder holds settings files written for one settings file version. Every
file here must keep passing the Settings Check tool in `--strict` mode, which
`tests/test_settings_checker.py` enforces. This is how existing settings files
are shown to keep working within a major pipeline version.

- Never edit these files. If one stops passing, the change that broke it is
  not backward compatible.
- Add a folder for each new settings file version, with at least one file
  that uses the fields that version introduces.

The `1.0/app-template.yml` file is the app template's settings with its
placeholders filled in, because the template's placeholder values fail
`--strict` on purpose.
