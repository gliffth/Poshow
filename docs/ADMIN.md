# Admin guide

## Becoming an admin
Set these environment variables (Render for the website/API, and the bot host for the bot):

| Variable | Meaning |
|---|---|
| `ADMIN_USERNAMES` | comma-separated **web usernames** (e.g. `Brown`) — they get an **Admin** section in Settings |
| `ADMIN_USER_IDS` | comma-separated **user ids** (a Telegram id works for the bot; web ids are shown by `/api/auth/me`) |

The check happens on the server from your signed login token — hiding the panel is only cosmetic, a normal
account calling the admin endpoints gets `403`.

## What admins can do
**Website → Settings → Admin**, or in Telegram:

- `/give <username|id> coins <n>` (negative takes credits away)
- `/give <username|id> item <name> <qty>` — e.g. `potion`, `revive`, `rare_candy`, `trade_cable`, `fire_stone`
- `/give <username|id> ball <pokeball|greatball|ultraball|masterball> <qty>`
- `/give <username|id> pokemon <species> [level] [shiny]` — lands on the team, or in storage if the team is full
- `/give <username|id> heal` — fully heals and revives the whole team
- `/whois <username|id>` — team, items, credits

If two players share a username the command refuses and lists their ids — use an id then.
Every admin action is written to the server log with who did it.

## Changing scene images
Settings → Admin → **Scene images**. Slots: `region_kanto … region_paldea`, `route`, `town`, `care_center`,
`starter_lab`, `gym`, `league`. Paste an `https://…` image link (or a path on the site such as `/scenes/kanto.png`
if you add the file under `public/scenes/`). Saving an empty link goes back to the built-in pixel scene.
(Requires the `site_assets` table from `database/schema.sql`.)
