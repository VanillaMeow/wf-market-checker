# wf-market-checker

Monitors [warframe.market](https://warframe.market/) for sell orders below a price you set — either a fixed platinum value or an automatically calculated threshold based on recent market averages.

When a matching order is found it copies a `/w` whisper message to your clipboard, optionally sends a Discord webhook notification, and can play an audio alert.

>[!Important]
>This app is **ran exclusively from source** with `uv`.

## Running from Source

You need to have the following dependencies installed:

- [Git](https://git-scm.com/install/)
- [uv](https://docs.astral.sh/uv/getting-started/installation/)

```sh
git clone https://github.com/VanillaMeow/wf-market-checker.git
cd wf-market-checker

# Run the app once to generate the config file
uv run app

# Edit the config file from the displayed path
# Run the app again with the same command
```

## Configuration

On first run, a `config.toml` file is generated in your platform's config directory.
The app will tell you where it was created. Open it in any text editor.

### General settings

| Key | Type | Default | Description |
| --- | --- | --- | --- |
| `do-audio-notification` | `bool` | `false` | Play a sound when a matching order is found. |
| `check-interval` | `float` | `1.0` | Seconds between each check cycle. The app respects warframe.market rate limits, so `1.0` is fine. |
| `webhook-url` | `string` | `""` | A Discord webhook URL for notifications. Leave as `""` to disable Discord notifications. |
| `ping-discord-ids` | `list[int]` | `[]` | Discord user IDs to ping in webhook messages (e.g. `[123456789, 987654321]`). |

### Item entries (`[[items]]`)

Each `[[items]]` block defines one item to watch. You can add as many as you want.

| Key | Type | Default | Description |
| --- | --- | --- | --- |
| `name` | `string` | *required* | The item's URL name on warframe.market (e.g. `molt_augmented`). You can find this in the URL: `warframe.market/items/<name>`. |
| `price-threshold` | `int` or `string` | *required* | The maximum platinum price to alert on. Can be a fixed number (e.g. `50`) or an auto-price window: `"2h"`, `"6h"`, or `"12h"` to use the average market price from that time window. |
| `profit-margin-percent` | `int` | `30` | When using auto-price, only alert if the order is at least this percent below the average. |
| `rank` | `int` or omitted | *none* | Mod rank filter. Only match orders at this rank. Omit for non-rankable items. |
| `quantity-min` | `int` | `-1` | Minimum quantity the seller must have listed. `-1` means no minimum. |

### Example: watching multiple items

```toml
webhook-url = 'https://discord.com/api/webhooks/your/webhook'
ping-discord-ids = [123456789]
check-interval = 1.0
do-audio-notification = true

# Alert if Molt Augmented rank 5 drops below the 2-hour average by 30%+
[[items]]
name = 'molt_augmented'
price-threshold = '2h'
profit-margin-percent = 30
rank = 5

# Alert if Vitality is listed at 5p or less
[[items]]
name = 'vitality'
price-threshold = 5

# Alert if Ammo Drum is being sold for 1p (quantity 2+)
[[items]]
name = 'ammo_drum'
price-threshold = 1
quantity-min = 2
```

## Notes

- The app respects warframe.market's rate limits, so a `check-interval` of `1.0` is fine.
- You may update the app with `git pull`.
- `git reset origin/HEAD --hard` if something goes very wrong.
- The codebase is strictly typed and fully compliant with [pyright](https://github.com/microsoft/pyright) and [ruff](https://docs.astral.sh/ruff/).
