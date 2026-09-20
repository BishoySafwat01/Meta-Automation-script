# Meta Business Automator — Rule Engine and Cross-Profile Synchronization Blueprint

Status: adversarially reviewed architecture blueprint; no runtime code is changed by this document.

Repository baseline: `main` at `e19f562` (`v6.4.1`). The worktree already contains unrelated in-progress changes in `bot_script.js`, `meta_inbox_userscript.user.js`, `qa_audit_runner.py`, and `qa_m1_focus_runner.py`; implementation must preserve and rebase around those changes.

## 1. Executive decision record

This design makes five decisions explicit:

1. `ultra_exact` is the default for every new rule. To follow the management mandate literally, the one-time v1-to-v2 migration changes every legacy rule's primary `matchType` to `ultra_exact`, including rules that historically serialized `contains`, `exact`, `word`, or `regex`. The pre-migration mode is recorded in the backup/migration report, and operators may explicitly switch away after migration.
2. `ultra_exact` compares the raw DOM-extracted customer message with the stored keyword using JavaScript strict string equality. It performs no trimming, case folding, Unicode normalization, Arabic normalization, whitespace collapsing, optional-prefix handling, or regex matching.
3. `id` identifies one local rule instance. `ruleCode` identifies the logical rule across profiles. Equal admitted `ruleCode` values are the linkage key; synchronized membership metadata distinguishes an intentional link from a newly imported collision. `isLinked` and `shared` are materialized informational flags, never the source of truth.
4. There is no central rule database or shared index. Discovery scans `profiles/{name}/config.json`; every profile remains independently portable and contains the complete rule data it needs to execute.
5. All profile writes use one host-side save/synchronization path. The desktop editor and injected browser HUD must not have separate persistence semantics.

Uniqueness is guaranteed within the local installation's profile root. It cannot be mathematically guaranteed across disconnected client installations without a central authority, so imported external profiles must be collision-checked on first load.

## 2. Forensic diagnosis of the current match pipeline

### 2.1 What is working

The desktop dropdown is bound correctly. `gui/app.js:599-601` writes the selected value into `rule.matchType`, and `gui/app.js:781-808` submits the full `state.currentConfig` to `save_profile_config`. The reported defect is therefore not primarily a missing desktop `change` listener.

The current `exact` branch also does not literally call `.includes()`. `bot_script.js:649-685` executes normalized equality, raw trimmed/case-insensitive equality, optional Arabic definite-article equivalence, then Unicode-property boundary regexes.

### 2.2 Actual causes of indistinguishable or misleading behavior

The observed symptom is produced by multiple defects and contract mismatches:

- `gui/app.js:376-378`, `gui/app.js:755-764`, and `gui/app.js:794` force missing and new modes to `contains`.
- `bot_script.js:625`, `bot_script.js:762`, and `bot_script.js:789` also default missing modes to `contains`.
- `bot_script.js:686-697` treats every unknown mode as `contains`. Merely adding `ultra_exact` to a dropdown today would make it execute substring matching, which is a fail-open defect.
- The standalone/injected HUD is a second editor. It creates `contains` rules at `bot_script.js:4536-4543` and exposes `contains`, `word`, and `exact`—but no `regex`—at `bot_script.js:4642-4646`. The desktop UI exposes `contains`, `exact`, and `regex`. These surfaces can serialize different semantics.
- `exact` and legacy `word` are aliases of the same branch. That branch normalizes Tashkeel, Hamza variants, Ta Marbuta, digits, case, and whitespace; it also treats an optional leading `ال` as equivalent. This makes many distinct Arabic inputs match.
- `regex` runs first against raw text and then against normalized text (`bot_script.js:636-639`). Literal regex patterns therefore often behave like normalized substring patterns.
- Runtime input is trimmed before matching at `bot_script.js:5359`, and keyword handling trims at `bot_script.js:628-629`. True whitespace-sensitive matching cannot be added until both losses are removed from the strict path.
- Documentation currently says `exact` matches the entire message (`EXECUTIVE_DEPLOYMENT_GUIDE.md:133`), while the implementation and new management requirement define it as a word-bounded search. Operators are comparing against the wrong documented contract.
- The browser HUD persists through `pySaveConfig`; `main.py:315-324` writes with `save_config`, which performs a direct non-atomic file write at `main.py:229-234`. This bypasses `ProfileManager`, atomic persistence, future cross-profile propagation, and any migration validator.

Current behavioral evidence from the checked-out matcher:

| Message | Keyword | contains | exact | regex literal | unknown / `ultra_exact` today |
|---|---|---:|---:|---:|---:|
| `السعر` | `سعر` | yes | yes | yes | yes (falls into contains) |
| `والسعر` | `سعر` | yes | no | yes | yes (falls into contains) |
| `سعره` | `سعر` | yes | no | yes | yes (falls into contains) |
| `سِعر` | `سعر` | yes | yes | yes | yes (falls into contains) |
| ` سعر ` | `سعر` | yes | yes | yes | yes (falls into contains) |

These results explain why ordinary operator tests make the modes look identical and prove that an unimplemented `ultra_exact` label would be dangerous.

## 3. Normative matching contract

The matching function must be an explicit exhaustive switch. Unknown values return no match and emit rate-limited telemetry; they must never fall through to `contains`.

| Mode | Input representation | Match rule | Deliberate non-match examples |
|---|---|---|---|
| `ultra_exact` | raw extracted message and raw stored keyword | `rawMessage === rawKeyword` | leading/trailing space, Tashkeel difference, Hamza difference, case difference, attached punctuation, attached Arabic letter, Unicode composition difference |
| `contains` | normalized message and normalized keyword | `normalizedMessage.includes(normalizedKeyword)` | a keyword absent after documented Arabic normalization |
| `exact` | normalized message and normalized keyword | escaped keyword/phrase bounded by `(^|[^\p{L}\p{N}\p{M}])` and `(?=$|[^\p{L}\p{N}\p{M}])`, flag `u` | keyword attached to an Arabic/Latin letter or digit |
| `regex` | raw message only | operator pattern in an isolated Worker with a hard timeout, flags `u` or `iu` according to `caseSensitive` | invalid, rejected, timed-out pattern, unavailable Worker, or a pattern that only matches normalized text |

For `contains` and `exact`, Arabic character normalization remains documented behavior. Latin case folding occurs only when `caseSensitive` is false; the normalizer must therefore stop lowercasing unconditionally. `ultra_exact` is always case-sensitive because case folding would violate character-for-character equality.

Normative pseudocode:

```js
switch (matchType ?? 'ultra_exact') {
  case 'ultra_exact':
    return rawKeywords.find(kw => isUsable(kw) && rawMessage === kw) ?? null;
  case 'contains':
    return normalizedContains(rawMessage, rawKeywords, caseSensitive);
  case 'exact':
    return unicodeWordBoundedMatch(rawMessage, rawKeywords, caseSensitive);
  case 'regex':
    return sandboxedRawRegexMatch(rawMessage, rawKeywords, caseSensitive);
  default:
    recordInvalidMode(matchType);
    return null;
}
```

Implementation constraints:

- `isUsable(kw)` may reject a zero-length or all-whitespace keyword, but it must compare the original stored string. It must not compare a trimmed copy.
- Do not use `DOM.extractTextWithAlt` as the strict input without refactoring it: that function currently injects synthetic spaces around every block element (`bot_script.js:949-956`). Add `DOM.extractMessageTextVerbatim`, scoped to the verified message-content node, that concatenates actual text-node values, emoji `alt` text, and explicit `<br>` newlines without adding wrapper whitespace or trimming. Feed that result to `ultra_exact`; keep a separate normalized/display extraction for presence checks, snippets, and logs.
- Preserve keyword strings as entered for `ultra_exact`. The current chip editor strips outer whitespace (`gui/app.js:483-487`), so it must stop doing that for strict rules and visibly represent leading/trailing spaces (for example, quoted chips plus a whitespace count) to prevent invisible operator mistakes. Legacy comma-delimited migration may retain its historical trimming behavior because the original raw separators are unrecoverable.
- The strict contract applies to the string produced by the DOM extractor. It does not claim byte-for-byte equality with Meta's network payload, which is not available to this engine.
- Remove the optional-`ال` equivalence from `exact`; it is fuzzy morphology, not a boundary rule.
- During the rolling upgrade, retain an explicit runtime-only `word -> exact` compatibility branch. It is a recognized legacy alias, not an unknown-mode fallback. Remove it only after all profiles report schema v2 migration complete; the v1-to-v2 management migration itself sets the rule's primary mode to `ultra_exact`.
- Keep `contextMatchType` independently configurable. Its compatibility default remains `contains` unless management separately mandates strict context matching.
- Update both `bot_script.js` and the byte-identical `meta_inbox_userscript.user.js` from one canonical source or a deterministic copy/build step. The existing parity test remains a release gate.
- Remove main-thread `RegExp.test` fallback from `RegexSandbox`. The current CSP/worker failure path calls heuristic-only synchronous evaluation (`bot_script.js:273-328`), which cannot provide a hard timeout. If the isolated Worker cannot be created, posted to, or restarted, regex returns false and emits a rate-limited capability warning.

### Required matcher truth table

At minimum, automated tests must establish:

- `ultra_exact("سعر", "سعر")` is true.
- `ultra_exact("سِعر", "سعر")`, `ultra_exact("سعر ", "سعر")`, `ultra_exact(" سعر", "سعر")`, `ultra_exact("سعره", "سعر")`, and `ultra_exact("سعر؟", "سعر")` are false.
- `ultra_exact("أ", "ا")` and `ultra_exact("ة", "ه")` are false.
- Canonically composed and decomposed Unicode strings are unequal unless their code-unit sequences are already identical.
- `contains("وسعره", "سعر")` is true.
- `exact("هل السعر مناسب؟", "السعر")` is true, while `exact("والسعر", "السعر")` is false because the left boundary is an Arabic letter.
- `regex("سعره", "^سعره$")` is true, while invalid and catastrophic patterns fail closed.
- Missing mode selects `ultra_exact`; unknown mode matches nothing.

## 4. Rule and profile JSON schema

Recommended canonical profile schema version: `2`.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://local.meta-automator.invalid/schema/profile-config-v2.json",
  "type": "object",
  "required": ["schemaVersion", "profileId", "configRevision", "rules", "config", "auto_start"],
  "properties": {
    "schemaVersion": { "const": 2 },
    "profileId": { "type": "string", "format": "uuid", "readOnly": true },
    "configRevision": { "type": "integer", "minimum": 0 },
    "rules": {
      "type": "array",
      "items": { "$ref": "#/$defs/rule" }
    },
    "config": { "type": "object" },
    "auto_start": { "type": "boolean", "default": false }
  },
  "additionalProperties": true,
  "$defs": {
    "matchType": {
      "type": "string",
      "enum": ["ultra_exact", "contains", "exact", "regex"]
    },
    "rule": {
      "type": "object",
      "required": [
        "id", "name", "ruleCode", "keywords", "contextKeywords", "reply",
        "matchType", "contextMatchType", "active", "isLinked", "shared", "sync"
      ],
      "properties": {
        "id": {
          "type": "string",
          "pattern": "^rule_[0-9a-f]{32}$",
          "readOnly": true,
          "description": "Immutable identity of this local rule instance only."
        },
        "name": {
          "type": "string",
          "minLength": 1,
          "maxLength": 160
        },
        "ruleCode": {
          "type": "string",
          "pattern": "^MBS-[0-9A-HJKMNP-TV-Z]{8}$",
          "readOnly": true,
          "description": "Immutable logical identity across local profiles."
        },
        "keywords": {
          "type": "array",
          "minItems": 1,
          "items": { "type": "string", "minLength": 1 }
        },
        "keyword": {
          "type": "string",
          "deprecated": true,
          "description": "One-release compatibility mirror generated from keywords."
        },
        "contextKeywords": {
          "type": "array",
          "items": { "type": "string", "minLength": 1 },
          "default": []
        },
        "contextKeyword": {
          "type": "string",
          "deprecated": true,
          "description": "One-release compatibility mirror generated from contextKeywords."
        },
        "reply": { "type": "string", "minLength": 1 },
        "matchType": { "$ref": "#/$defs/matchType", "default": "ultra_exact" },
        "contextMatchType": { "$ref": "#/$defs/matchType", "default": "contains" },
        "caseSensitive": { "type": "boolean", "default": false },
        "active": { "type": "boolean", "default": true },
        "isLinked": {
          "type": "boolean",
          "default": false,
          "readOnly": true,
          "description": "Derived: this ruleCode occurs in more than one profile."
        },
        "shared": {
          "type": "boolean",
          "default": false,
          "readOnly": true,
          "description": "Compatibility/UI alias of isLinked; not linkage authority."
        },
        "sync": {
          "type": "object",
          "required": ["revision", "updatedAt", "updatedByProfileId", "operationId", "memberProfileIds"],
          "properties": {
            "revision": { "type": "integer", "minimum": 0 },
            "updatedAt": { "type": "string", "format": "date-time" },
            "updatedByProfileId": { "type": "string", "format": "uuid" },
            "operationId": { "type": "string", "format": "uuid" },
            "memberProfileIds": {
              "type": "array",
              "uniqueItems": true,
              "items": { "type": "string", "format": "uuid" }
            }
          },
          "additionalProperties": false
        }
      },
      "additionalProperties": true
    }
  }
}
```

Example linked rule instance:

```json
{
  "id": "rule_a4590bf55d4c4f8caa0063ed15ad0f8d",
  "name": "استفسار سعر المشد - ليبيا",
  "ruleCode": "MBS-7K2M9Q4X",
  "keywords": ["سعر المشد"],
  "keyword": "سعر المشد",
  "contextKeywords": ["ليبيا"],
  "contextKeyword": "ليبيا",
  "reply": "السعر الحالي ...",
  "matchType": "ultra_exact",
  "contextMatchType": "contains",
  "caseSensitive": false,
  "active": true,
  "isLinked": true,
  "shared": true,
  "sync": {
    "revision": 4,
    "updatedAt": "2026-09-20T12:00:00Z",
    "updatedByProfileId": "3d87c0a3-36d0-47a5-a9e2-88be96ec0af7",
    "operationId": "3c4b0308-a0e8-49f7-b318-4c9e642b501d",
    "memberProfileIds": [
      "3d87c0a3-36d0-47a5-a9e2-88be96ec0af7",
      "1d709319-ed98-4f8a-bc24-514959e69e8e"
    ]
  }
}
```

### Identity and generation rules

- Generate `id` with `uuid.uuid4().hex` and prefix `rule_`. Cloning always creates a new `id`; linking also creates a new local `id` in the destination.
- Generate `ruleCode` as eight Crockford Base32 characters after `MBS-`. Scan every readable profile config and retry on collision. Eight characters provide roughly 40 bits while remaining operator-friendly; four decimal digits cannot satisfy a uniqueness contract.
- Preserve valid existing codes. Reject two instances with the same code inside one profile; a profile cannot contain two local representations of one logical rule.
- Require `profileId` uniqueness within the profile root. A folder admitted with a duplicate `profileId` is treated as a copied profile: assign a fresh `profileId` under the catalog lease and do not infer linkage until its rule-code collisions are resolved.
- Each rule's synchronized `memberProfileIds` records the profile identities intentionally admitted to that logical link. A newly discovered/imported folder whose rule code collides but whose `profileId` is absent from the existing membership is quarantined from synchronization until the operator explicitly chooses “link matching codes” or “recode as independent.” Code equality is authoritative only after admission; this prevents an accidental cross-install collision from silently linking unrelated rules without introducing a central catalog.
- A rule code is read-only after persistence. “Enter an existing code” is implemented as a dedicated creation/link action, not by making the code field editable on an existing card.
- `name`, `active`, `id`, and local ordering remain profile-local. They are not synchronized.
- The exact synchronized allowlist is `keywords`, `reply`, `contextKeywords`, and `matchType`, as mandated. Compatibility mirrors `keyword` and `contextKeyword` are regenerated from the canonical arrays. No other field propagates implicitly.

### Migration contract

`ProfileManager` owns migration; render functions must stop mutating schema defaults.

For each `schemaVersion < 2` profile:

1. Create a same-profile backup such as `config.pre-v2.backup.json` once.
2. Add `profileId`, `configRevision`, and `schemaVersion`.
3. Preserve a unique valid `id`; otherwise generate a local ID.
4. Add a non-empty name using the first keyword or `قاعدة #N` as the deterministic fallback.
5. Add a globally collision-checked `ruleCode`. Codes newly generated for unrelated legacy rules must always differ across profiles so migration cannot create accidental links.
6. Convert `keyword` and `contextKeyword` into arrays if arrays are missing. Continue writing compatibility mirrors for one release.
7. Record each prior primary match mode in the migration report, then set every legacy rule's primary `matchType` to `ultra_exact` as mandated. Keep a temporary runtime `word -> exact` alias only so an interrupted/rolling migration does not disable an unmigrated profile. Runtime handling of every other unknown mode remains fail-closed.
8. Initialize `isLinked`, `shared`, and `sync`; an independent migrated rule begins with only its own `profileId` in `memberProfileIds`. Then scan the complete profile root and derive linked flags from admitted code multiplicity.
9. Validate and write with `atomic_write_json` while holding the appropriate lease authority.

Migration must be idempotent, independently retryable per profile, and never scan or package profiles outside the resolved client-local profile root. The pre-v2 backup is for migration recovery only; it must never be used to roll back later v2 edits.

## 5. Synchronization engine in `profile_manager.py`

### 5.1 Components

Add these host-side concepts:

- `RuleSchemaMigrator`: canonicalizes and validates v1/v2 configs.
- `RuleCodeAllocator`: scans local configs and produces collision-free codes.
- `LinkedRuleIndex`: ephemeral mapping `ruleCode -> [(profileName, ruleIndex, ruleSnapshot)]`; rebuilt from profile files on each mutating operation or safely cached behind file fingerprints. It is never persisted as a shared database.
- `ProfileCatalogLease`: a short-lived OS lock at `profiles/.sync.lock` that serializes profile-root membership snapshots, migration, code allocation, create/import/admission, rename/delete, and coordinated commit preparation. It is a lock only—not a database or rule store.
- `ProfileSyncCoordinator`: the only entry point for profile config mutation and import.
- `SaveResult`: structured result containing the complete canonical source config, source revision, changed profiles, non-persisting runtime-apply payloads, warnings, and per-profile failures.
- `LeaseAuthority`: an unforgeable in-process capability representing the lifetime `ProfileLease` already held by a running worker.

### 5.2 Save algorithm

```text
Desktop/HUD save(profile, submittedConfig, expectedConfigRevision)
  -> acquire ProfileCatalogLease
  -> canonicalize + validate submitted config
  -> scan every profile config and build LinkedRuleIndex
  -> reject duplicate ruleCode within a profile
  -> reject stale source configRevision
  -> for each cross-profile code in the submitted profile:
       reject a stale rule sync revision
       compare a canonical hash of the synchronized allowlist with the stored source
       if changed, copy only the synchronized allowlist into target snapshots
       assign max(link revisions)+1 and one operationId to every changed instance
  -> recompute isLinked/shared for every affected instance
  -> acquire non-owned ProfileLeases in sorted absolute-path order
       running workers owned by this process contribute LeaseAuthority instead
       any external/busy lease aborts before the first write
  -> prepare every complete JSON document
  -> increment configRevision in every document that will be written
  -> create per-profile operation recovery snapshots
  -> atomic_write_json(source and every target)
  -> release all acquired leases
  -> release ProfileCatalogLease
  -> return canonical source config and runtime-apply payloads
  -> dispatch APPLY_RULE_SNAPSHOT only after all locks are released
```

Important invariants:

- Never wait for a Playwright/page command while holding the catalog or a file/profile lease.
- Never recursively call `save_profile_config` while propagating. One coordinator call computes and writes the entire mutation set.
- The universal lock order is catalog lease first, then profile leases in stable lexicographic absolute-path order. Use non-blocking profile acquisition. If any non-owned profile is busy, release acquired locks and return `LINKED_PROFILE_BUSY` without writing anything.
- Keep the catalog lease across the membership snapshot, allocation, validation, and disk commit so a concurrent process cannot add, rename, or delete a profile between discovery and write. All profile CRUD paths obey the same catalog lease.
- A running worker already owns a lifetime `ProfileLease`. The coordinator must reuse an explicit in-process lease capability; it must not blindly bypass a lock based only on a profile name or PID.
- Multi-file replacement cannot be fully transactional across a process crash. Each file is atomic, and `sync.operationId` plus `sync.revision` makes the operation idempotent and repairable. Before replacement, create a bounded per-operation recovery snapshot inside each affected profile; remove it only after the full commit is durably complete. Startup reconciliation applies the unique highest revision to lagging copies or uses the same-operation snapshots for repair. If equal highest revisions contain different payload hashes, fail closed and request operator conflict resolution.
- Source-wins applies only to a non-stale save. `configRevision` prevents an old desktop form from overwriting a newer local profile, and per-rule `sync.revision` prevents stale linked content from overwriting a newer linked copy.
- Saving an unrelated profile setting or local-only rule field must not increment linked revisions or rewrite linked payloads. Every profile document changed by propagation increments its own `configRevision`, invalidating stale open editors for that profile.
- Disk is authoritative. A failed live reload does not roll back durable files; return `reloadFailures` and retry. Restart/navigation must read current disk state.

### 5.3 Running workers and live reload

`ProfileManager` should remain independent of Playwright. `DesktopBridgeApi.save_profile_config_v2` invokes the coordinator, receives runtime apply payloads, and then uses `send_page_command(profile, 'APPLY_RULE_SNAPSHOT', fullRulesArray)` for every affected running profile. This command updates in-memory rules, `window.__INITIAL_RULES__`, localStorage, and the HUD display, but it must not call `saveRules`, `pySaveConfig`, or any persistence callback. The existing `RELOAD_RULES` handler currently calls `saveRules()` and would create a save -> reload -> save feedback loop; host-driven reload must therefore be non-persisting by construction.

The current worker captures its `settings` object at startup, and navigation reinjection reuses it. Therefore live reload alone is insufficient: a later navigation can restore stale rules. Implement one of these equivalent contracts:

- preferred: `on_reloaded()` re-reads `ProfileManager.get_profile_config(profile_name)` before every injection; or
- maintain a controller-owned `settings_by_profile` cache and replace its rules after every successful save/sync.

The first option is simpler and makes disk the sole truth.

The injected HUD's `pySaveConfig` handler must call the same `ProfileSyncCoordinator`; remove direct `main.save_config` writes. Treat HUD edits as a versioned rule/settings patch merged into the host's current canonical profile, not as a whole-document replacement that could erase `profileId`, codes, or sync metadata. Inject the current `configRevision` into the page and reject a stale patch. The existing desktop-side “save then reload source only” logic must be replaced by the structured result so the bridge, not the UI, applies all affected workers exactly once.

Backward API contract: keep `ProfileManager.save_profile_config(name, data) -> bool` as a compatibility wrapper that invokes the coordinator and returns `True` only on a complete durable save. Add `save_profile_config_result(name, data, expected_revision, lease_authorities) -> SaveResult` for the v2 bridge and patch paths. Likewise, expose versioned bridge methods such as `save_profile_config_v2` and `save_rule_patch_v2`; do not silently change existing Python callers that assert `is True`. Both old and new entry points perform linked propagation—the legacy wrapper is not a bypass.

On success, `SaveResult.canonicalSourceConfig` contains the complete host-generated state, including new local IDs, rule codes, derived flags, sync revisions, and `configRevision`. The desktop must atomically replace `state.currentConfig` with this value before rendering or allowing another edit. Every target document changed by propagation also increments `configRevision`, so any open editor for that target receives a stale-revision error until it reloads.

Regression invariant: one operator save produces exactly one coordinated disk mutation and at most one non-persisting runtime apply per affected worker; it produces zero inbound HUD save callbacks.

### 5.4 Failure behavior

Return structured errors instead of `true`/`false`:

```json
{
  "ok": false,
  "code": "LINKED_PROFILE_BUSY",
  "message": "A linked profile is owned by another application instance.",
  "sourceProfile": "Libya",
  "blockedProfiles": ["Egypt"],
  "changedProfiles": []
}
```

Other stable codes: `CATALOG_BUSY`, `STALE_CONFIG_REVISION`, `STALE_LINK_REVISION`, `DUPLICATE_PROFILE_ID`, `DUPLICATE_RULE_CODE`, `PROFILE_ADMISSION_REQUIRED`, `INVALID_RULE`, `RULE_CODE_COLLISION`, `PARTIAL_CRASH_RECOVERY_REQUIRED`, and `LIVE_RELOAD_FAILED`.

### 5.5 Deletion, unlink, rename, and profile lifecycle

The coordinator diffs the stored source rule-code set against the submitted canonical set, not only codes that remain present.

- Deleting one linked rule is a local unlink/delete by default. Surviving instances remain complete; their `isLinked/shared` flags are recomputed, and the last survivor becomes unlinked.
- “Delete linked rule everywhere” is a separate explicit destructive operation with a confirmation listing all affected profiles. It is not implied by deleting a card.
- “Unlink but keep copy” assigns the selected instance a fresh `ruleCode`, retains its local `id` and content, resets sync metadata, and recomputes flags on the old code's survivors.
- Profile deletion removes that profile's memberships, then recomputes and durably writes linked flags for surviving profiles in the same root-coordinated operation. Rename changes only the folder/name reference; immutable `profileId` and rule codes remain unchanged.
- Manual folder removal is detected on the next catalog scan; survivor flags are repaired before the next link mutation. Manual folder arrival goes through the admission/collision quarantine described above.
- Create, admission, rename, delete, import, migration, and code allocation all take the catalog lease, preventing membership races with saves.

## 6. Import, clone, and link design

### 6.1 Desktop APIs

Expose narrow operations rather than asking JavaScript to merge raw configs:

- `list_import_sources(target_profile)` -> profile summaries excluding the target.
- `list_importable_rules(source_profile)` -> `id`, `name`, `ruleCode`, linked status, and a safe preview.
- `import_rules(source_profile, target_profile, source_rule_ids, mode, expected_target_revision)`.
- `link_rule_by_code(target_profile, draft_rule, existing_rule_code, expected_target_revision)`.

All operations execute inside `ProfileSyncCoordinator` and return `SaveResult`.

When profiles are imported from outside the current root, admission occurs before rule import. Duplicate `profileId` is regenerated. Colliding rule codes are not treated as links until the operator chooses link or independent recoding; independent recoding assigns fresh codes to every colliding logical rule under the catalog lease.

### 6.2 Clone mode

For every selected rule:

- copy editable content;
- create a fresh local `id`;
- create a fresh collision-checked `ruleCode`;
- set `isLinked=false`, `shared=false`, and sync revision `0`;
- preserve the source name with a localized “copy” suffix if necessary;
- never establish later propagation to the source.

### 6.3 Link mode

For every selected rule:

- create a fresh local `id` in the target;
- preserve the source `ruleCode` and synchronized payload;
- retain a profile-local editable name and active flag;
- mark all instances of that code linked in the same coordinated write;
- if the target already has that code, do not insert a duplicate—report it as already linked and offer update/skip semantics.

Entering an existing code while creating a rule uses `link_rule_by_code`. The host must resolve exactly one logical code, populate the synchronized fields from the highest non-conflicting revision, and only then persist. The saved card displays the code read-only.

## 7. Desktop UI design

### Rules toolbar (`gui/index.html`)

Add a top-level secondary action in `#tab-rules`:

`استيراد / نسخ قواعد من صفحة أخرى`

Keep Save as the primary action. Disable import when no target profile is selected or fewer than two profiles exist.

### Import modal

The modal contains:

1. Source profile selector.
2. Searchable multi-select rule list showing name, code, and linked badge.
3. Required mode selector:
   - `نسخ كقواعد مستقلة` — fresh IDs and codes.
   - `ربط بالقواعد الأصلية` — fresh local IDs, preserved codes.
4. Collision summary (`already linked`, `name conflict`, `invalid legacy rule`).
5. Confirm/cancel controls and an operation result summary.

The UI sends IDs and mode only. It never generates authoritative codes or edits another profile's JSON directly.

### Rule card (`gui/app.js`)

Header layout:

`قاعدة #X: [name] (كود: MBS-7K2M9Q4X)`

- `name` is an editable text input with length validation.
- `ruleCode` is a selectable/read-only value with a copy button.
- show a `مرتبطة` badge when the server-derived `isLinked` is true.
- provide a dedicated `ربط بكود موجود` action only for an unsaved draft or explicit relink workflow; never unlock the persisted code input.
- add `ultra_exact` as the first/default dropdown option with an Arabic description that says character-for-character and whitespace-sensitive.
- relabel `exact` as Arabic word/phrase boundaries, not whole-message equality.
- show an inline warning for `regex` and validate before save.
- for `ultra_exact`, preserve keyword whitespace and display invisible leading/trailing whitespace explicitly so the operator can verify the value that will be compared.

`renderRulesUI()` must be pure rendering. Schema migration and defaulting belong to the host. `btnAddRule` may construct an optimistic draft with `matchType: 'ultra_exact'`, but the host generates `id` and `ruleCode` when the draft is persisted.

The embedded HUD must either become read-only for rule structure or expose the same four modes and metadata. If editing remains enabled, it must use identical labels, defaults, validation, and the unified host save path.

## 8. Isolation and security guarantees

- Delivery archives continue to exclude all profile directories and client configs.
- All scans are rooted at `ProfileManager.base_dir`; validated profile names and resolved paths may not escape it.
- No global `rules.json`, SQLite database, cloud API, or monolithic index is introduced.
- A copied profile folder remains executable by itself because every linked rule is fully materialized, not a reference to another profile.
- Link synchronization is best-effort only across profiles presently under the same local root. Moving one profile away intentionally breaks future propagation without breaking execution.
- Unknown schema versions, unknown match types, duplicate codes within one profile, ambiguous highest revisions, invalid regexes, and lock ownership uncertainty all fail closed.
- Regex runs only in the hardened isolated-Worker path with a hard timeout; Worker/CSP failure returns no match. Strict and literal modes never invoke regex.
- Telemetry must not log full customer messages, full replies, or config bodies. Log profile name, rule code, operation ID, revision, and error code only.

## 9. Phased zero-regression implementation plan

The repository has no GitHub CLI installed, so the plan is executable as local branches/commits and can later be pushed through the project's normal review mechanism. Use `codex/` branch prefixes if branches are created. Because the current worktree is dirty in both runtime scripts, preserve or finish that work before starting a branch that touches them.

### Step 1 — Freeze behavioral contracts and characterization tests

Context: Current tests cover normalization, ReDoS, and compound priority but do not distinguish every match mode.

Tasks:

- Add a table-driven Node harness for the normative matrix, including whitespace, Arabic variants, attached letters, punctuation, invalid modes, regex raw-only behavior, and Worker-unavailable fail-closed behavior. Mark only the not-yet-implemented normative assertions as explicit expected failures in this preparatory commit; Step 2 removes every marker.
- Add serialization tests proving dropdown values survive desktop save and live reload.
- Add tests that both runtime artifacts remain byte-identical.
- Update the documentation assertion for `exact` semantics.

Verification:

```bash
python3 qa_audit_runner.py
python3 audit_system.py
```

Exit: The suite remains green, current behavior is characterized, and each desired-but-unimplemented assertion is visibly marked expected-failure. No expected-failure marker may survive Step 2. Rollback: tests/documentation only.

### Step 2 — Implement matcher semantics and strict defaults

Context: This step changes only runtime matching/default paths, not profile linking.

Tasks:

- Refactor `testKeywordsMatch` into an exhaustive switch.
- Add a verbatim message extractor with no synthetic block padding, and preserve raw message and keyword strings for `ultra_exact`.
- make `exact` Unicode word-bounded without optional-`ال` fuzziness.
- make regex raw-only and fail closed.
- retain an explicit runtime-only `word -> exact` compatibility alias until migration completeness is proven.
- change every new/missing rule default in desktop UI, embedded HUD, JS fallback rules, and Python fallback rules to `ultra_exact`.
- align both dropdowns to the four canonical modes.
- generate/synchronize the userscript artifact deterministically.

Verification:

```bash
python3 qa_audit_runner.py
python3 audit_system.py
cmp -s bot_script.js meta_inbox_userscript.user.js
```

Exit: Full truth table passes with zero expected-failure markers; no unknown value can execute `contains`; `word` is the sole documented temporary compatibility alias. Rollback: revert the matcher/default commit; no schema migration has run yet.

### Step 3 — Add schema v2 migration and identity allocation

Context: Profiles remain self-contained; this creates metadata without linking unrelated rules.

Tasks:

- Implement schema constants, canonicalizer, validator, `profileId`, revisions, UUID local IDs, collision-checked `ruleCode` allocation, catalog lease, and external-folder admission/quarantine in `profile_manager.py`.
- Implement idempotent backup and migration.
- record prior modes and migrate every legacy primary `matchType` to `ultra_exact`; keep the runtime `word` alias until every profile is confirmed v2, then remove it in the next release boundary.
- add tests for rerun idempotence, corrupt configs, duplicate profile IDs, duplicate rule-code quarantine, concurrent collision retries, and zero cross-profile accidental links.

Verification:

```bash
python3 -m unittest discover -s tests -p 'test_profile_schema*.py'
python3 qa_audit_runner.py
```

Exit: Mixed v1/v2 fixtures migrate deterministically, every migrated legacy rule is strict, and backups restore cleanly before any subsequent v2 edit. Rollback: a pre-v2 backup may be restored only during the migration transaction or before post-migration edits; later rollback requires export plus a forward compensating migration.

### Step 4 — Implement synchronized disk propagation and lease protocol

Context: This is the core multi-file mutation engine and must be tested without Playwright first.

Tasks:

- Implement the ephemeral index, coordinator, optimistic revisions, strict allowlist merge, linked flag derivation, operation IDs, and structured results.
- implement catalog-first lock ordering, ordered non-blocking profile lease acquisition, and in-process `LeaseAuthority` reuse.
- implement startup reconciliation and ambiguous-revision fail-closed behavior.
- implement local delete/unlink, explicit delete-everywhere, unlink-keep-copy, profile rename/delete flag repair, and per-operation recovery snapshots.
- test source-wins, stale rejection, target busy abort-before-write, partial-crash repair, profile deletion, rename, manual folder admission/removal, and two-process allocation/save races.

Verification:

```bash
python3 -m unittest discover -s tests -p 'test_profile_sync*.py'
python3 qa_audit_runner.py
```

Exit: No successful save leaves linked payloads divergent; no busy external profile is written; catalog membership cannot change during discovery/commit. Rollback: stop new linked mutations and run forward reconciliation from per-operation recovery snapshots/current v2 configs; never restore the migration backup over post-migration edits.

### Step 5 — Unify bridge persistence and live reload

Context: Current desktop saves and injected-HUD saves take different disk paths, and navigation can reuse stale startup settings.

Tasks:

- Route `DesktopBridgeApi.save_profile_config` and `pySaveConfig` through the coordinator.
- return the complete canonical source config in structured `SaveResult`, and atomically replace desktop `state.currentConfig` after success.
- re-read disk before navigation reinjection.
- dispatch one non-persisting `APPLY_RULE_SNAPSHOT` command per affected running profile after lease release.
- merge versioned HUD patches host-side so they cannot erase schema metadata.
- test stopped/running/mixed linked sets, generated-code rehydration, zero reload-save feedback, reload failure, navigation after reload, and two app instances.

Verification:

```bash
python3 -m unittest discover -s tests -p 'test_live_rule_reload*.py'
python3 qa_audit_runner.py
```

Exit: A linked edit updates every disk file and every locally running engine without restart; one save causes one coordinated write and zero HUD persistence callbacks; a later navigation cannot resurrect stale rules. Rollback: stop workers, disable linked editing, and continue from durable disk configs.

### Step 6 — Implement metadata, import/clone/link UI

Context: Host APIs are authoritative before the UI exposes the workflow.

Tasks:

- Add import/list/link bridge APIs and test collision behavior.
- add toolbar action and modal in `gui/index.html`, styles in `gui/styles.css`, and state/events in `gui/app.js`.
- add editable name, read-only code, linked badge, and exact header layout.
- make card rendering non-mutating and handle structured save/reload errors.
- align or restrict the embedded HUD editor.

Verification:

```bash
python3 qa_audit_runner.py
python3 audit_system.py
```

Manual acceptance:

- clone A -> B creates different IDs and codes and future edits do not propagate;
- link A -> B creates different IDs, the same code, and edits propagate both directions on save;
- linking by an existing code populates canonical synchronized fields and locks the code;
- a running B changes behavior immediately after A is saved;
- Arabic RTL layout remains readable at minimum window size.

Exit: Every specified UI path uses host APIs and communicates conflicts without silent partial success. Rollback: hide import/link actions; existing v2 rules continue to run.

### Step 7 — Release hardening and packaging audit

Tasks:

- Add a release fixture with at least three profiles: independent, cloned, and linked rules.
- run matcher, migration, catalog concurrency, two-process code allocation, lifecycle, crash-recovery, Windows lease, Worker-failure regex, userscript parity, canonical-save-result, and no-feedback-loop live reload suites.
- inspect delivery ZIP contents and assert zero profile directories, `config.pre-v2` backups, or test data.
- update README and executive deployment guide with the exact mode table, linkage scope, recovery behavior, and portability contract.

Verification:

```bash
python3 qa_audit_runner.py
python3 audit_system.py
python3 -m unittest discover -s tests
unzip -l Meta_Automation_<version>_Delivery.zip
git status --short
```

Exit: clean release candidate, full green suite, and archive audit proving zero client profiles. Rollback: retain the previous signed delivery archive; for client data, use migration-transaction restore only before v2 edits, otherwise execute a tested forward compensating migration from current configs/recovery snapshots.

## 10. Dependency graph and parallelism

```text
Step 1 tests/contracts
  -> Step 2 matcher/defaults
  -> Step 3 schema/identity
      -> Step 4 disk synchronization
          -> Step 5 bridge/live reload
              -> Step 6 UI/import
                  -> Step 7 release hardening
```

The sequence is intentionally mostly serial because the same rule contract crosses JavaScript, Python, disk, and live runtime. Within steps, UI markup/styles can be prepared in parallel with bridge API tests after Step 4's API contract is frozen. Do not parallel-edit `bot_script.js` and `meta_inbox_userscript.user.js`; edit/generate one canonical artifact and verify byte parity.

## 11. Plan mutation protocol

- If a step exposes a contract flaw, update this document and its truth tables before changing code.
- Splitting a step requires preserving its original exit criteria across the replacement steps.
- New schema fields require an explicit migration, downgrade, portability, and synchronization classification.
- New synchronized fields require management approval and an allowlist test; they must never be added by copying the whole rule object.
- A step may be skipped only when its exit criteria are already proven by committed tests.
- Record material design changes in a short decision note under this document rather than relying on commit messages alone.
- Migration backups are never generic rollback points. After any v2 edit, rollback is a forward compensating operation from current canonical configs and per-operation recovery snapshots.

## 12. Final acceptance gates

The upgrade is complete only when all are true:

- The four modes produce observably distinct, documented results.
- `ultra_exact` is genuinely raw and whitespace-sensitive end to end.
- Missing mode defaults strict; unknown mode fails closed.
- Every persisted rule has a local ID, name, and collision-checked immutable code.
- Clone and link modes satisfy their identity contracts.
- Saving any linked instance propagates only the approved fields to every local linked profile.
- Running linked profiles reload without restart, and navigation does not restore stale rules.
- External lease contention causes a no-write failure, not deadlock or partial normal-operation propagation.
- A profile folder remains runnable when copied alone.
- Newly admitted folders cannot silently link through duplicate profile IDs or ambiguous rule-code collisions.
- One host save cannot trigger a runtime-apply persistence loop.
- Delivery archives contain zero client profiles and zero migration backups.

## 13. Adversarial review gate

The review identified and this revision resolves the following release-blocking classes: non-persisting live apply, canonical save rehydration, profile-root catalog serialization, rolling `word` compatibility, literal legacy-default compliance, deletion/unlink lifecycle, imported identity collision quarantine, Worker-only regex execution, and non-destructive rollback guidance. Implementation review must re-check these nine contracts against tests before release.
