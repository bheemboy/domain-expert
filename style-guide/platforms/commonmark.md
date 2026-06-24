# Platform profile: CommonMark

Use this profile for plain CommonMark output and for renderers that resolve
relative file links using the source file path (most static-site generators
and code-hosting viewers outside of Docusaurus).

---

## Internal link form

Keep the `.md` extension in internal doc links.

- **Do:** `[Security model](./security/security-model.md)`
- **Don't:** `[Security model](./security/security-model)`

Plain CommonMark renderers resolve relative file links with the extension
present; omitting it produces a broken link.

---

## Anchor links

Link to a section within a page by appending the anchor derived from the
heading text: lower-case the heading, replace spaces with hyphens, and drop
punctuation.

- **Example:** `[See also](./page.md#section-heading)`

---

## Admonitions

Plain CommonMark has no admonition block syntax. Represent admonitions as
blockquotes with a bold inline label.

| Severity | Form |
|----------|------|
| Note     | `> **Note:** …` |
| Warning  | `> **Warning:** …` |
| Tip      | `> **Tip:** …` |
| Important | `> **Important:** …` |
| Caution  | `> **Caution:** …` |

Keep the label in title case and follow it with a colon. Admonition text
follows on the same line.
