# MLA TPM-less protected signer — owner-approved conditional redesign (2026-11-19 KST)

## Evidence and authorization
Owner-supplied **real Windows Local Operator** output: `tpm_present=false`, `tpm_ready=false`, `tpm_enabled=false`; Defender `DEFENDER_ACTIVE_READONLY`; fixed protected directory `HOLD_PATH_UNAVAILABLE`. These are local observations, **not** evidence that TPM hardware physically does not exist or that the OS principal can yet be trusted. Owner explicitly approved a TPM-less CNG **design/source alternative** on 2026-11-19. No OS account, TPM, registry, ACL, CNG key, SCM service, Defender, original data or Production change is authorized solely by this approval.

## Decision: explicit CNG KSP profile, no automatic fallback
Retain current `Microsoft Platform Crypto Provider` (`TPM_V1`) as the default for existing installs. Add protected 64-bit HKLM `SOFTWARE\MyLocalAI\ProtectedBrokers\v1\KeyProviderMode` REG_SZ with **only**:
- `TPM_V1`: Microsoft Platform Crypto Provider, require CNG implementation flag HARDWARE, existing nonexport policy/EC-P256/key/public-key/signature checks.
- `SOFTWARE_CNG_OWNER_APPROVED_V1`: Microsoft Software Key Storage Provider, require CNG implementation flag SOFTWARE and not HARDWARE/REMOVABLE; require existing **machine** ECDSA-P256 key, signing-only usage and **no export policy**, supported key security descriptor and restrictive key ACL. All four key roles (OwnerUI, owner service, reviewer, scanner) pin the same explicit profile but **different** keys, public blobs, SIDs, images and guarded folders. Neither model input nor a Controller flag, environment variable, HKCU key, registry auto-probe or `Get-Tpm` can enable a mode or mint a signature.
- Absent `KeyProviderMode` means TPM-only for backward compatibility, **not** software fallback. Unrecognized/type-mismatched pin is immediate HOLD. Code does not provision any keys or change HKLM.

### Security model and honest limitation
Software KSP can enforce its Windows ACL and non-export *policy* but **cannot assert TPM-backed private-key isolation or physical nonextractability**; a compromised elevated OS/admin/key-isolation environment is outside this lower-assurance protection. Do not label SOFTWARE as TPM equivalent, `HARDWARE_ATTESTED`, `P2_VERIFIED` or F18-certified. Separate protected Windows local principals, locked HKLM/ancestor and machine-key ACL, pinned EXE+bundle, own-session OwnerUI one-use UI signature, strict nonce/lease/SHA/owner scope, separate reviewer identity, immutable Git and deny-by-default remain mandatory. If one control is unavailable -> HOLD; never allow same-process self-review or generated-code execution.

### Windows live provisioning gate — distinct scoped owner GO required
Before any use, separately authorize an operator reviewed provisioning plan with explicit account names/SIDs, install destination and backup/restore; four machine CNG non-exportable signing-only key names and ACL/security descriptors; four pinned public keys and four EXE hashes; protected shared/role folders and SQLite; restricted SCM services; OwnerUI own active user session and key; action-scoped revocation and emergency rollback. No general Administrator or Everyone broad allow ACE. Account/keys/ACL/HKLM/SCM setup is **NOT_RUN** and must not be executed by untrusted commands or software without owner approval. Read-only preflight with `MATCHED_UNATTESTED` never constitutes this gate.

### SWU ownership and progress
This is a **redesign within existing MLA-SWU-008 (REQ-07)**, with MLA-SWU-021 (REQ-14/15) and CS-SWU-012 still separate. No new required SWU or denominator adjustment, and no preemptive 2+2 failure. Legacy `52/55`; additive Local Operator `3/3`; total `55/58 = 94.83%` source candidates before any new acceptance evidence. MLA-SWU-008 remains `BLOCKED_TRUST` until actual independently protected account, pinned KSP keys, live OwnerUI request/response and security preflight; implementation work can be `SOURCE_PARTIAL`. P2 accepted evidence remains 0/58 recorded / **formal UNASSESSED**, P2 LOCKED, release HOLD.

### Acceptance matrix
1. P1: deterministic profile validation and HKLM-pinned KSP routing, typed Provider/Key property checks; no fallback when TPM unavailable; OwnerUI and all service signing paths identical; missing/mismatched ACL/signature/nonce/lease HOLD; minimum pure/mock tests plus syntax and high-risk negative tests.
2. P2: real 64-bit registry owner/ACL; restricted software machine key ACL/private-key export denial; authenticated native pipe Controller SID; OwnerUI own logged-on SID and one-use signature; nonce replay/revocation/SCM trust/security regression; Windows integrity/Defender clean state, independent protected reviewer policy.
3. Critical REQ-14 independent **executed tests** remain blocked by Zero-VM/no untrusted-generated-code execution. STATIC_ONLY cannot close REQ-14; separate approval/design needed.
4. Backout: leave existing TPM profile, original keys and receipts untouched; no auto-migrate/delete or software profile auto-activate; backup first and restore only by separately approved operator.

Official references:
- https://learn.microsoft.com/en-us/windows/win32/api/ncrypt/nf-ncrypt-ncryptopenstorageprovider
- https://learn.microsoft.com/en-us/windows/win32/seccng/key-storage-property-identifiers
- https://learn.microsoft.com/en-us/windows/win32/seccertenroll/cng-key-storage-providers
