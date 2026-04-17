## Summary

<!-- What does this PR do? One or two sentences. -->

## User surface impact

<!-- What changes for end-users (kids, teens, adults) in their daily flow?
     "None" is a valid answer. If new UI is added, describe what members see. -->

## Admin surface impact

<!-- What changes for admins or permission-holders?
     New config options? New permission keys? New admin screens? -->

## Dual-surface compliance checklist

- [ ] Every new action this PR adds that mutates state calls `actor.require_permission(...)` on the backend
- [ ] Every new UI button/control that triggers an admin-level action is gated with `useHasPermission(...)` on the frontend
- [ ] Any new feature-configurable value is stored in `family_config` or `member_config`, NOT hardcoded in `seedData.ts` or a constants file
- [ ] Any new permission key is granted to the appropriate role tiers via a new migration (append-only; no editing existing migrations)
- [ ] Admin-only UI surfaces live under `scout-ui/app/admin/*`
- [ ] Genuinely public backend endpoints (no auth required) are annotated with `# noqa: public-route`
- [ ] `npx tsc --noEmit` passes from `scout-ui/`
- [ ] `python -m pytest tests/` passes from `backend/`
- [ ] `node scripts/architecture-check.js` exits 0 (or all warnings are documented below)

## Architecture check output

<!-- Paste the output of `node scripts/architecture-check.js` here.
     If warnings are present, explain each one:
       - Is it a false positive? (add # noqa: public-route to the endpoint and re-run)
       - Is it a real gap? (fix it before merge, or document it in ARCHITECTURE.md Known Gaps) -->

```
(paste arch-check output here)
```

## Test plan

- [ ] <!-- Step a reviewer can take to verify the user-surface change -->
- [ ] <!-- Step a reviewer can take to verify the admin-surface change -->
- [ ] <!-- Any manual smoke steps for features that lack automated coverage -->
