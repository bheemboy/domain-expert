# Story Personas

How to choose the persona for a story. These skills ship a small **default
roster**; a host wiki may override it (see "Configurable roster" below).

## Why personas matter

Every story's Description opens with "As a [persona], I want [capability] so
that [benefit]." The persona is the target user whose perspective the A/C is
written from. The wrong persona produces A/C that tests the wrong viewpoint.

## Default roster

| Persona | Use for |
|---------|---------|
| **user** | Day-to-day operational stories — running work, viewing status, routine actions. |
| **admin** | Configuration and management stories. The default for most stories. |
| **support engineer** | Troubleshooting, diagnostics, recovery, remote assistance. |

Other personas (platform/sysadmin, provisioning, account admin, SRE/infra)
appear only when a story is squarely in their area — infer them from the
objective and the wiki's `entities/`, and confirm with the user.

## Selection rules

- **Default to `admin`** — most stories benefit the administrator.
- **Use `user`** for daily-operation stories.
- **Use `support engineer`** for troubleshooting/recovery stories.
- **Use a rarely-used persona** only when the story is squarely in its area.
- **Never use "developer" as a target persona** — "As a developer, I want a
  migration" is a task, not a story (see Common Mistakes in story-format.md).
- **Ask if unclear** — if you cannot determine the persona from the objective
  and the wiki, ask the user.

## Configurable roster (seam)

If the host wiki defines a `personas:` list in `wiki.config.yaml`, use that
roster instead of the default above. (Not required in v1; the default roster
applies when the key is absent.)
