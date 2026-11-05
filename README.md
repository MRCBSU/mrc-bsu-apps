# MRC BSU app index

This repository holds the index page listing our organisation's Shiny apps.
Changes merged into `main` are published to shinyapps.io automatically.

## Adding your app

1. Create a branch.
2. Run, from the repository root:

   ```bash
   python add_app.py --name "My App" \
     --url https://mrc-bsu.shinyapps.io/my-app/ \
     --description "One line on what it does" \
     --app-dir index-app --skip-deploy
   ```

   Use `--panel panel2` for **Covid-19 Support**, otherwise leave blank.
   The script checks your URL responds before adding it. Keep `--skip-deploy`:
   publishing happens automatically after review.

3. Commit `index-app/apps.json`, push, and open a pull request.

The checks on your pull request confirm the list is valid and your URL is live.
Once it's approved and merged, the index page is republished within a few minutes.

You can also edit `index-app/apps.json` directly instead of running the script.
