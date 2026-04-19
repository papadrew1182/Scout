# Phase 4 Handoff - Home Maintenance OS

**Branch:** `sprint/operability-phase-4-home-maintenance`
**Date:** 2026-04-19

---

## Migrations added

- `042_home_maintenance.sql` - Schema: home_zones, home_assets, maintenance_templates, maintenance_instances
- `043_home_maintenance_permissions.sql` - Permission keys: home.manage_zones, home.manage_assets, home.manage_templates, home.complete_instance, home.view

## Permission keys added

| Key | Tiers |
|-----|-------|
| `home.manage_zones` | PARENT, PRIMARY_PARENT |
| `home.manage_assets` | PARENT, PRIMARY_PARENT |
| `home.manage_templates` | PARENT, PRIMARY_PARENT |
| `home.complete_instance` | YOUNG_CHILD, CHILD, TEEN, PARENT, PRIMARY_PARENT |
| `home.view` | YOUNG_CHILD, CHILD, TEEN, PARENT, PRIMARY_PARENT |

## Tables added

- `scout.home_zones` - zone registry (room/area/outdoor)
- `scout.home_assets` - asset tracking with warranty/manual
- `scout.maintenance_templates` - recurring maintenance with scope contracts
- `scout.maintenance_instances` - generated maintenance tasks

## Endpoints added

| Endpoint | Permission |
|----------|-----------|
| `GET /home/zones` | `home.view` |
| `POST /home/zones` | `home.manage_zones` |
| `GET /home/assets` | `home.view` |
| `POST /home/assets` | `home.manage_assets` |
| `GET /home/templates` | `home.view` |
| `POST /home/templates` | `home.manage_templates` |
| `GET /home/instances` | `home.view` |
| `POST /home/instances/{id}/complete` | `home.complete_instance` |
| `POST /home/generate-upcoming` | `home.manage_templates` |

## Frontend files added

- `scout-ui/app/(scout)/home/index.tsx` - user home screen
- `scout-ui/app/admin/home/index.tsx` - admin tabbed interface

## Known follow-ups

- Roberts family zone pack seeding (deferred - requires running seed_smoke.py)
- Scheduled auto-generation (manual endpoint shipped, cron deferred)
- /today "Home today" section integration
- Photo uploads for manuals/receipts

## Narrative summary

Phase 4 introduced the home maintenance domain with four new tables,
five permission keys, nine endpoints, and user + admin frontend screens.
The template-instance pattern mirrors the chore system from Phase 3.
A manual generate-upcoming endpoint creates instances from active
templates. The admin screen uses a tabbed interface for zones, assets,
and templates.
