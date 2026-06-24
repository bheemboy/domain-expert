# Story Examples

These are **domain-neutral teaching examples**. They use generic nouns ("the
device", "the management portal", "an Admin") to illustrate the format without
tying to any product. For real, product-specific reference stories, load the
host project's worked examples from its domain context (see SKILL.md → Domain
context).

The two examples below show both common shapes: a device/operational story and a
portal CRUD story. Study how A/C stays user-facing, how implementation detail
lands in D/N, how Q/N gives test guidance, and how `Note:` and `Background` are
used.

## Contents
- Reset a device locally without removing it from the portal
- Import and view trusted certificates in the portal

---

## Story: Reset a device locally without removing it from the portal

**Description:** As a Support engineer, I want to reset a device locally without removing its portal record so that I can restore it to factory defaults while preserving its registration history. The existing reset flow depends on network connectivity which can fail mid-process, leaving the device in an indeterminate state.

*Background*
The existing reset downloads and runs a full re-install from the portal, introducing network and CDN dependencies that can fail mid-run. This story introduces a self-contained local reset that needs no network. It is validated with the simplest end-to-end flow: a support engineer accesses a registered device, runs the reset, and after reboot the device re-registers automatically with its existing portal record. Removal-triggered reset and portal-side changes are handled in later stories.

*A/C*
1. A user with local or console access can reset a registered device without first removing it from the portal.
2. After reset and reboot, the device re-registers with its existing portal record automatically and becomes available for use without any manual registration step or setup-code entry.
3. Reset completes successfully even when the device has no network connection. No internet or portal access is required during the reset itself.
4. After reset, device configuration (excluding hostname) returns to default values, and the local admin password is reset to default. Installed software versions are unchanged — the same components present before the reset are present after.
5. No activity log entries are written by the reset at any point — not when it starts, and not when it completes.
    Note: Reset must be silent in the audit trail because it is a recovery action, not a tracked user operation.

*D/N*
1. Reset the local admin password unconditionally as the very first operation, before any other work begins. It must not be guarded by any condition that could cause it to be skipped.
2. Before clearing any item, back up identity material (device identity, certificates, private keys), the local config files, and pending audit entries to a timestamped directory before clearing begins.
3. The backup is for engineering/support troubleshooting, not for end users.

*Q/N*
1. On a registered device, run the reset without removing it from the portal. Confirm it re-registers automatically after reboot and becomes available without setup-code entry.
2. Test offline reset: disconnect the network, run the reset from the console, confirm backup and reset steps all complete, then reconnect and confirm re-registration.
3. Confirm no activity log entries are written during or after reset (pair this with test 1, which confirms the positive outcome of successful re-registration).
4. Confirm installed component versions and hostname are unchanged immediately after reset.

---

## Story: Import and view trusted certificates in the portal

**Description:** As an Admin, I want to import and view custom trusted certificates in the management portal so that my devices can securely trust and connect to internal backend servers using internal or self-generated certificates.

**A/C:**
1. Administrators with the "Edit Certificates" privilege can import a new certificate. The import action is not available to users without that privilege.
2. Import accepts certificate content in PEM format and requires a name for the entry.
3. A full certificate chain can be provided; when multiple certificates are supplied, unique names are derived from the provided name.
4. The admin can optionally preview a certificate before importing.
5. After a successful import, the certificate list shows the imported entries.
6. Activity log entries record the import action.
7. An error is shown when incorrectly formatted content is submitted.
    Note: Importing an expired certificate is allowed — expiry is not a validation failure.

**D/N**
1. Import is launched from the toolbar button, or from a "click here" link shown when the list is empty.
2. The import dialog shows "Name" (unique) and "Certificate Data" (multi-line). Help text for Certificate Data: `Paste a certificate in X.509 PEM format here.`
3. Validate name and certificate data before adding: invalid certificate data is rejected with an error; a duplicate name is rejected with an error.
4. The dialog can parse the certificate data and preview Common Name, Issuer, and Expiration Date before adding.
5. Follow existing UI standards — the list's default sorting and filtering behavior must work.

**Q/N**
1. As an admin with the privilege, import a single valid certificate and confirm it appears in the list. Repeat without the privilege and confirm the import action is unavailable.
2. Import a full chain with one provided name and confirm unique names are derived.
3. Submit malformed content and confirm the error; submit an expired-but-valid certificate and confirm it is accepted.
4. Confirm the activity log records the import.
