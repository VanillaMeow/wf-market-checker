# wf-market-checker

- Python app that monitors [warframe.market](https://warframe.market/) for items listed below a specified price threshold.

- When a suitable order is found it send a discord webhook notification, copies a whisper message to the clipboard,
and prints the message to the console.

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

## Notes

- The app is aware of warframe.market's rate limits, so you may lower the `CHECK_INTERVAL` to like 1s.
- You may update the app with `git pull`.
- `git reset origin/HEAD --hard` if something goes very wrong.
