# BirdLense UX canonical map

[Русский](./UX_CANONICAL_MAP.ru.md)

This map defines the primary route for each role and task after the UX reset.

## Roles

| Role | Primary routes | Main goal |
|------|----------------|-----------|
| `guest` | `/`, `/timeline`, `/species`, `/migration-calendar`, `/species-directory`, `/species/:id`, `/live`, `/food` | Observe birds, browse recordings, inspect species pages. (`/species` and `/migration-calendar` are the same seasonality UI.) |
| `contributor` | guest routes + `/timeline?review=1` | Correct uncertain detections and improve recognition quality. |
| `admin` | contributor routes + `/settings`, `/system`, `/library` | Configure the station, maintain data, and use service tooling. |

## Primary user journeys

1. First station setup
   - `/settings`
   - Cameras and recording sources
   - Notifications and integrations
   - Recognition tuning
   - `/system` to confirm healthy status

2. Find and inspect a recording
   - `/timeline`
   - Pick a recorded day
   - Open a visit
   - `/videos/:id`

3. Find a bird species
   - `/species` (or `/migration-calendar` — same screen) for the seasonality table; `/species-directory` for card browse
   - Search species
   - `/species/:id`
   - Back to `/timeline?speciesId=<id>` for source recordings

4. Correct recognition
   - `/timeline?review=1`
   - Open recording evidence
   - Confirm or correct the species
   - `/system` recognition improvement when enough corrections exist

5. Service and archive maintenance
   - `/system` for health, diagnostics, recognition improvement
   - `/library` for archive, exports, storage, replay, maintenance

## Route meanings

| Route | Meaning |
|-------|---------|
| `/timeline` | Everyday recordings workflow |
| `/timeline?review=1` | Review queue for uncertain detections |
| `/species` | Seasonality grid (visits × species × month); primary nav **Species** |
| `/migration-calendar` | Same component as `/species` (alias URL) |
| `/species-directory` | Card-style species directory |
| `/settings` | Station setup and outcome-based configuration |
| `/system` | Service overview and support tools |
| `/library` | Data archive and maintenance |
