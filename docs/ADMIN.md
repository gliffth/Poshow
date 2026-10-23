# Admin guide

## Becoming an admin

Set these on the API host and on the bot host:

| Variable | Meaning |
|---|---|
| `ADMIN_USERNAMES` | Comma-separated web usernames. They get an Admin section in Settings. |
| `ADMIN_USER_IDS` | Comma-separated user ids. A Telegram id works for the bot; `/api/auth/me` shows a web account's id. |

The server checks the signed login token. Hiding the panel is cosmetic: a normal account calling an admin endpoint
receives `403`.

## What admins can do

On the website (Settings → Admin) or in Telegram:

- `/give <username|id> coins <n>` (a negative number removes coins)
- `/give <username|id> item <name> <qty>`, for example `potion`, `revive`, `rare_candy`, `trade_cable`, `fire_stone`
- `/give <username|id> ball <pokeball|greatball|ultraball|masterball> <qty>`
- `/give <username|id> pokemon <species> [level] [shiny]`: added to the team, or to storage if the team is full
- `/give <username|id> heal`: fully heals and revives the team
- `/whois <username|id>`: team, items and coins

If two players share a username the command refuses and lists their ids; use an id. Admin actions are written to
the server log with the acting account.

## Scene images

Settings → Admin → Scene images. Slots: `region_kanto` to `region_paldea`, `route`, `town`, `care_center`,
`starter_lab`, `gym`, `league`. Enter an `https://` image URL, or a path such as `/scenes/kanto.png` for a file under
`public/scenes/`. Saving an empty value restores the built-in scene. Requires the `site_assets` table from
`database/schema.sql`. Changes appear immediately for the admin and within the cache lifetime
(`ASSETS_CACHE_S`, 60 s) elsewhere.

## Endpoints

| Endpoint | Returns |
|---|---|
| `GET /api/admin/feedback` | Bug reports and ideas sent from Settings. |
| `GET /api/metrics` | Request and database timing since the last restart. |
| `GET /api/admin/db-health` | Database-side statistics. |
| `GET /api/admin/db-explain` | Execution plan of a named query. |
