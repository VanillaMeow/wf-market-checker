# wf-market-checker

Python script that monitors warframe.market for items listed below a specified price threshold.

When a suitable order is found, send a discord webhook notification, copies a whisper message to the clipboard,
and prints the message to the console.

## Running from Source

You need to have the following dependencies installed:

- [Git](https://git-scm.com/install/)
- [uv](https://docs.astral.sh/uv/getting-started/installation/)

```sh
git clone https://github.com/VanillaMeow/wf-market-checker.git
cd wf-market-checker

# Edit the src/config.py file to match your needs
code ./src/config.py

# Finally, run the app
uv run -m src
```

## Notes

- The app is aware of warframe.market's rate limits, so you may lower the `CHECK_INTERVAL` to like 1s.
- I only intend for this to be ran from source with `uv`, don't ask for any kind of distribution.
- `src/config.py` is in .gitignore, so you may update the app with `git pull`.
- `git reset origin/HEAD --hard` if something goes very wrong.
