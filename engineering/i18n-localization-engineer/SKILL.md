---
name: "i18n-localization-engineer"
description: "Audit, implement, and maintain internationalization (i18n) and localization (l10n) across any codebase. Use when adding multi-language support, extracting hardcoded strings, managing locale files, or handling RTL layouts."
---

# i18n Localization Engineer

## Overview

Use this skill when adding internationalization to an existing codebase, auditing for hardcoded strings, scaffolding locale files, or enforcing l10n conventions across a project. It covers web (React, Vue, Angular), backend (Node.js, Python, Go), and mobile (React Native, Flutter) stacks.

## Core Content

### Phase 1 — Audit existing strings

Run `scripts/check-hardcoded-strings.py` first. It walks the source tree and emits every user-visible string that bypasses your i18n layer:

```bash
python3 scripts/check-hardcoded-strings.py --src ./src --ext tsx,ts,jsx,js
python3 scripts/check-hardcoded-strings.py --src ./src --json > audit.json
```

Only act on strings that users will read. Skip log messages, internal IDs, enum values, and URLs.

### Phase 2 — Choose one i18n library and commit to it

| Stack | Recommended library |
|-------|---------------------|
| React | `react-intl` (ICU messages, plural rules) |
| Vue | `vue-i18n` |
| Angular | `@angular/localize` |
| Node.js | `i18next` |
| Python | `gettext` / `Babel` |
| Go | `golang.org/x/text` |
| React Native | `react-intl` + Metro config |
| Flutter | `flutter_localizations` |

Do not mix libraries in one project. Pick one and enforce it via linting.

### Phase 3 — Extract strings with a key naming convention

Use the `{namespace}.{component}.{descriptor}` pattern:

```
auth.login.title          → "Sign in to your account"
auth.login.emailLabel     → "Email address"
auth.login.submitButton   → "Continue"
errors.validation.required → "This field is required"
```

Rules:
- Keys are dot-separated lowercase camelCase segments.
- Namespaces map 1:1 to feature directories.
- Never use the English copy as the key (`"Sign in"` as key → rejected).
- Plural forms get a `.one` / `.other` suffix: `cart.items.one`, `cart.items.other`.

### Phase 4 — Build the locale file structure

```
locales/
├── en/
│   ├── auth.json
│   ├── errors.json
│   └── cart.json
├── fr/
│   └── ...
└── ar/          ← RTL locale
    └── ...
```

English is always the source locale. Every other locale file must have the same key set as `en/`. Missing keys fall back to English silently — do not ship a locale until it is ≥ 90 % complete.

### Phase 5 — Handle special formatting

**Numbers and currency** — Never hardcode `$` or `,`. Use the `Intl.NumberFormat` API (JS) or your library's `<FormattedNumber>` component:

```tsx
<FormattedNumber value={price} style="currency" currency="USD" />
```

**Dates** — Use `Intl.DateTimeFormat` or `<FormattedDate>`. Store all dates as UTC ISO 8601; format at render time only.

**Plurals** — Use ICU plural syntax, not ternary operators:

```json
{ "cart.items": "{count, plural, one {# item} other {# items}}" }
```

**Gender** — Use ICU select syntax:

```json
{ "profile.greeting": "{gender, select, female {She} male {He} other {They}} joined." }
```

### Phase 6 — RTL support

For Arabic, Hebrew, Persian, Urdu: set `dir="rtl"` at the HTML root, not on individual elements. Use CSS logical properties (`margin-inline-start`, `padding-inline-end`) instead of `margin-left`. Mirror icons that have directional meaning (arrows, progress bars). Never flip text, logos, or non-directional icons.

> See [references/rtl-checklist.md](references/rtl-checklist.md) for a full RTL QA checklist.

### Phase 7 — Automate locale-key sync

Add a CI step that:
1. Extracts all keys from source (`react-intl` babel plugin or `i18next-parser`).
2. Diffs against each locale file.
3. Fails the build if any locale is missing > 10 % of keys or contains orphaned keys not present in source.

```bash
# example with i18next-parser
npx i18next-parser --config i18next-parser.config.js --fail-on-warnings
```

## Anti-Patterns

**Never concatenate translated strings.** Word order differs across languages.

```tsx
// ❌ broken in German, Japanese
t('You have') + ` ${count} ` + t('messages')

// ✅ correct
t('inbox.messageCount', { count })   // "You have {count} messages"
```

**Never use index-based plurals.** `messages[count === 1 ? 0 : 1]` breaks for zero, dual, and many plural categories (Arabic has six).

**Never store the display locale in the database.** Store the user's locale preference as a BCP 47 tag (`en-US`, `fr-FR`). Format at render time, not at write time.

**Never put HTML inside translation strings** unless your library explicitly sanitizes it. Use rich text components instead:

```tsx
// ❌ XSS risk
t('terms', { link: '<a href="/terms">terms</a>' })

// ✅ safe
<FormattedMessage id="terms" values={{ link: chunks => <a href="/terms">{chunks}</a> }} />
```

**Never skip locale testing.** Pseudolocalization (replacing characters with accented equivalents) catches layout breaks before translators are involved. Enable it in dev:

```bash
LOCALE=en-x-pseudo yarn dev
```

## Cross-References

- [engineering/security-guidance](../security-guidance/SKILL.md) — sanitize translated strings in HTML contexts
- [engineering/feature-flags-architect](../feature-flags-architect/SKILL.md) — gate locale rollouts behind flags
- [engineering/slo-architect](../slo-architect/SKILL.md) — add locale-coverage SLO to CI
- [engineering/docker-development](../docker-development/SKILL.md) — mount locale files as volumes in dev containers
