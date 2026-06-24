# Platform profile: Docusaurus

This is the default profile. When no platform profile is specified, these
conventions apply.

---

## Internal link form

Omit the `.md` or `.mdx` extension from internal doc links.

- **Do:** `[Security model](./security/security-model)`
- **Don't:** `[Security model](./security/security-model.md)`

The extensionless form is required inside JSX elements (for example `<mark>`)
as well as in plain Markdown links. Inside JSX the renderer leaves the
extension literal, which produces a broken URL.

---

## Slug links

When a page sets a custom `slug:` in its frontmatter, link to the slug
rather than the file path. The platform resolves links against the served
URL, not the source file path.

- **Example:** if `introduction.md` has `slug: /`, link as `[Introduction](/)`,
  not `[Introduction](./introduction)`.

---

## Admonitions

Use the fenced-block syntax. Five types are supported:

```
:::note
:::tip
:::info
:::warning
:::danger
```

An optional title may follow the fence opener on the same line. Use
sentence case for the title.

- **Do:** `:::warning Unsaved changes are lost`
- **Don't:** `:::WARNING UNSAVED CHANGES ARE LOST`

The generic `R-ADMON` label vocabulary (Note, Tip, Important, Caution, Warning) maps to Docusaurus as: Note→`:::note`, Tip→`:::tip`, Important→`:::info`, Caution/Warning→`:::warning`, and `:::danger` for the most severe cases. Use `:::info` wherever the guide calls for "Important" — the label differs but the intent is the same.
