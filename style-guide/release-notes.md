# Release notes, versioning, deprecation (R-RELNOTES)

Load when authoring or reviewing a release-notes page. Aligned to **Semantic
Versioning 2.0.0** (`semver.org`) and **Keep a Changelog 1.1.0**
(`keepachangelog.com`).

## Versioning

- **R-RELNOTES-01:** Use `MAJOR.MINOR.PATCH`. Increment MAJOR for incompatible changes, MINOR for backward-compatible additions, PATCH for backward-compatible fixes.

- **R-RELNOTES-02:** Pre-release versions use a hyphen suffix: `2.0.0-rc.1`, `2.0.0-beta.2`.

- **R-RELNOTES-03:** Publish patch releases when shipping fixes between minor releases. Don't roll patch fixes silently into the next minor release.

## Page structure

- **R-RELNOTES-04:** The release-notes page opens with a short header stating the product name, that the project follows Keep a Changelog and Semantic Versioning (with links), and a pointer to the upgrade guide.

- **R-RELNOTES-05:** Each release is a level-2 heading in Keep a Changelog format: `## [x.y.z] - YYYY-MM-DD`. Example:

  ```
  ## [1.3.0] - 2026-04-15
  ```

  Square brackets around the version, ISO 8601 date (`YYYY-MM-DD`), separated by a hyphen with single spaces. Use the same format for every release on the page.

- **R-RELNOTES-06:** Order releases newest first. An `## [Unreleased]` section at the top of the page tracks changes accumulated for the next release; no date.

- **R-RELNOTES-07:** Each release uses these section headings (H3), in this order, omitting any with no entries:
  1. **Added** — new features.
  2. **Changed** — changes to existing functionality (including performance, infrastructure, dependency upgrades the customer observes).
  3. **Deprecated** — features still working but slated for removal.
  4. **Removed** — features removed in this release.
  5. **Fixed** — bug fixes.
  6. **Security** — security-relevant fixes.

  Don't invent additional section names ("Enhancements", "Infrastructure", "Defects fixed", "New features"). Map everything into the six above.

  Known issues are not a Keep a Changelog section. Maintain a separate Known Issues page; link from the release header.

## Entry shape

- **R-RELNOTES-08:** Each entry is a bullet beginning with a verb matching its section. Sentence case. End with a period. One line per entry where possible. Past tense is conventional for shipped releases; present tense is acceptable where it reads more naturally.
  - **Added:** "Added support for the reporting add-on v1.7."
  - **Changed:** "Changed the activation timeout from 30 s to 60 s."
  - **Deprecated:** "Deprecated the legacy V1 activation API."
  - **Removed:** "Removed the legacy V1 activation API."
  - **Fixed:** "Fixed registration failing when the network interface is renamed."
  - **Security:** "Fixed an authentication bypass in the activation endpoint."

- **R-RELNOTES-09:** Issue references in parens at the end. Multiple references comma-separated.
  - **Do:** "Fixed registration failing when the network interface is renamed. (#1336029)"
  - **Don't:** "1336029 - Registration fails when renaming NICs"

- **R-RELNOTES-10:** Use nested bullets for sub-details:
  ```
  - Added support for additional add-ons:
    - Reporting add-on v1.7.
    - Analytics add-on v2.0.
  ```

- **R-RELNOTES-11:** Prefer stating what the release did rather than addressing the reader directly inside an entry. If customer action is needed, use an Action required callout (R-RELNOTES-15). Where a second-person phrasing is the clearest option, it is acceptable.

## Deprecation

- **R-RELNOTES-12:** A deprecation entry should cover: what is deprecated, how to migrate, and when removal is planned. A common shape is: `Deprecated <feature>. <Migration guidance>. Removal planned for <version>.`
  - **Example:** "Deprecated the legacy V1 activation API. Use `/v2/activation` instead (see [API reference](...)). Removal planned for 2.0.0."
  - If the removal release isn't committed: "Removal planned for a future major release."

- **R-RELNOTES-13:** Deprecation entries appear in the release that *introduces* the deprecation, not in every subsequent release. Maintain a separate "Deprecated features" reference page.

- **R-RELNOTES-14:** Removed entries cross-reference the deprecation release and migration path: "Removed the legacy V1 activation API (deprecated in 1.3.0). Use `/v2/activation`."

## Action required and breaking changes

- **R-RELNOTES-15:** When a release requires customer action (config migration, manual restart, certificate rotation, irreversible data migration), add an **Action required** callout at the top of the release, immediately after the date heading:

  ```
  > **Action required:** <one sentence summary>. See [<upgrade topic>](...).
  ```

  Don't bury action-required guidance inside an Added/Changed/Removed bullet.

- **R-RELNOTES-16:** Major-version releases warrant a dedicated **Upgrading from \<prev-major\>** subsection with migration steps at the top of the release.

- **R-RELNOTES-17:** Every breaking change has a one-sentence migration path in its entry or a link to a migration topic.

## Security

- **R-RELNOTES-18:** Security entries lead with the CVSS v3.1 severity label: Critical, High, Medium, or Low. CVE identifier in parens if assigned. A common format is `[Severity]` in brackets before the entry text, though the exact bracket style may follow your platform's conventions.
  - **Example:** "[High] Fixed an authentication bypass in the activation endpoint. (CVE-2026-12345)"
  - State the issue, not exploit details.

## What not to include

- **R-RELNOTES-19:** No marketing language ("revolutionary", "powerful", "delighted to announce").

- **R-RELNOTES-20:** No contributor names or commit hashes in customer release notes. Issue numbers are fine.

- **R-RELNOTES-21:** Keep release notes as their own reference document, separate from product guides. Embedding a changelog inside a user guide creates information-architecture duplication and maintenance overhead; prefer a link to the release notes page instead.

- **R-RELNOTES-22:** Don't change the meaning of published release entries. Typo and link fixes are fine. Meaning changes go in the next release as a correction.

## Example release block

```markdown
## [1.3.0] - 2026-04-15

> **Action required:** Certificates must be rotated before upgrade. See [Upgrade to 1.3](...).

### Added
- Added integrated online help in the admin console. (#1340022)
- Added support for additional add-ons:
  - Reporting add-on v1.7.
  - Analytics add-on v2.0.

### Changed
- Changed the activation timeout from 30 s to 60 s to accommodate slower networks. (#1339814)
- Improved dashboard loading time by ~40% on large fleets.

### Deprecated
- Deprecated the legacy V1 activation API. Use `/v2/activation` instead (see [API reference](...)). Removal planned for 2.0.0.

### Fixed
- Fixed registration failing when the network interface is renamed. (#1336029)
- Fixed activity log export truncating at 10,000 rows. (#1338201)

### Security
- [High] Fixed an authentication bypass in the activation endpoint. (CVE-2026-12345)
```
