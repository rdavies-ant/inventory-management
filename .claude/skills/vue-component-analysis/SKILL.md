---
name: vue-component-analysis
description: Analyze Vue 3 component structure and suggest optimizations for performance and code reuse. Use this skill when reviewing or refactoring .vue files in client/src, or when asked to assess a component's quality, reactivity, or reusability.
---

# Vue Component Analysis

This skill provides a structured way to analyze Vue 3 (Composition API) components in the Factory Inventory Management System and recommend concrete improvements. Use it when reviewing an existing `.vue` file, before a refactor, or when a component "feels" slow or hard to maintain.

## When to use

- A view or component in `client/src/` needs a quality review.
- A component is slow, re-renders too often, or duplicates logic found elsewhere.
- You're about to extract shared logic and want to confirm the boundaries.
- Onboarding to an unfamiliar component and want a fast structural map.

## Analysis checklist

Work through these dimensions in order. For each finding, cite the specific line and give a concrete fix — never a vague "consider improving."

### 1. API style consistency

- **Must be Composition API.** This project standardizes on `setup()` with `ref`/`computed`. Flag any component using the Options API (`data()`, `methods:`, `mounted()`) — it should be converted.
- Flag mixing of Options and Composition API in the same file.

### 2. Reactivity correctness

- **Derived data must be `computed`, not recomputed in methods or duplicated in `ref`s.** Look for values that are assigned from other reactive state inside a watcher or method — those are usually a `computed` in disguise.
- Verify `.value` is used in `<script>` and omitted in `<template>`.
- Flag `ref`s that are written but never read, or state that could be local instead of module-level.

### 3. Rendering performance

- **`v-for` keys must be stable unique IDs** (`item.id`, `item.sku`, `month`), never the array index. Index keys cause incorrect DOM reuse when the list changes.
- Heavy calculations in the template or in methods should move to `computed` (cached) — especially anything called once per row.
- Prefer `v-show` over `v-if` for elements toggled frequently.
- Watch for `O(n²)` patterns (e.g. recomputing a max/sum inside a per-row function — hoist it to a `computed`).

### 4. Code reuse

- **Shared state belongs in a composable** (`composables/useX.js`), not copy-pasted across views. This repo already has `useFilters`, `useI18n`, `useAuth` — check whether the component reinvents any of them.
- Repeated formatting (currency, dates) should use the shared utilities (`utils/currency.js`) and `useI18n`, not inline logic.
- API calls must go through the centralized `api.js` client, never `axios` directly in a component.

### 5. Internationalization

- All user-facing strings must use `t('...')` from `useI18n`, with keys present in **both** `locales/en.js` and `locales/ja.js`.
- Currency must use the locale-aware helpers and `currentCurrency`, never a hardcoded `$`.

### 6. Loading / error / empty states

- Confirm the standard pattern: `loading` → `error` → data, each handled in the template.
- Confirm there's a graceful empty state (no rows / no results).

### 7. Hygiene

- No leftover `console.log` / debug statements.
- Dates validated before `.getMonth()`/`.getTime()` calls.
- Props are not mutated directly (emit events instead).

## Output format

Produce a short report:

1. **Structure** — one-line summary of what the component does, its data sources, and key computed values.
2. **Findings** — a prioritized list. For each: `file:line` · severity (high/medium/low) · the issue · the concrete fix.
3. **Reuse opportunities** — logic that should move to a composable or shared util, and where it already exists.
4. **Quick wins** — the 1–3 highest-value changes to make first.

## Reference patterns

Good components to mirror in this repo: `views/Orders.vue`, `views/Demand.vue` (Composition API, `useFilters` + `useI18n`, `computed`-derived data, `api.js` calls, stable `v-for` keys). Use these as the baseline when judging another component.
