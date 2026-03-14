# Daily Digest Automation

Automatically curates a daily email digest on topics you care about, using Claude as an autonomous research agent backed by Brave Search. Runs every morning via GitHub Actions and delivers a formatted HTML email to your Gmail inbox.

## How it works

1. Claude reads your topics from `config.yaml`
2. For each topic, Claude autonomously makes 2–4 Brave web searches
3. Claude synthesizes the results into a concise markdown summary
4. The summaries are rendered into a styled HTML email
5. The email is sent to your inbox via Gmail SMTP

## Prerequisites

- A GitHub account (free)
- An [Anthropic API key](https://console.anthropic.com/)
- A [Brave Search API key](https://brave.com/search/api/) — free tier: 2,000 queries/month
- A Gmail account with **2-Step Verification enabled**

## Step 1 — Get a Brave Search API key

1. Go to [brave.com/search/api](https://brave.com/search/api/) and click **Get started for free**
2. Create an account and choose the **Free** plan
3. Copy your API key from the dashboard

## Step 2 — Get a Gmail App Password

> App Passwords require 2-Step Verification to be enabled on your Google account.

1. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
2. Sign in and select **Mail** as the app and **Other** as the device (name it "Daily Digest")
3. Click **Generate** and copy the 16-character password shown

## Step 3 — Customize your topics

Edit `config.yaml` to set the digest title and your topics:

```yaml
digest:
  title: "My Daily Digest"

topics:
  - name: "AI & LLMs"
    description: "Latest in large language models, AI safety, new model releases"

  - name: "Formula 1"
    description: "Race results, team news, driver standings, technical updates"

  - name: "Personal Finance"
    description: "Market movements, investing insights, personal finance tips"
```

Add as many topics as you like. Each becomes its own section in the email.

## Step 4 — Local setup (optional, for testing)

```bash
git clone <this-repo>
cd nonlynear
pip install -r requirements.txt
cp .env.example .env
# Edit .env and fill in all values
python digest.py
```

To preview the HTML without sending an email:

```bash
DEBUG_MODE=true python digest.py
```

## Step 5 — GitHub Actions setup

1. Push this repository to GitHub
2. Go to **Settings → Secrets and variables → Actions → New repository secret**
3. Add these 5 secrets:

| Secret name | Value |
|---|---|
| `ANTHROPIC_API_KEY` | Your Anthropic API key |
| `BRAVE_API_KEY` | Your Brave Search API key |
| `GMAIL_USER` | Gmail address used to send (e.g. `myname@gmail.com`) |
| `GMAIL_APP_PASSWORD` | The 16-char App Password from Step 2 |
| `RECIPIENT_EMAIL` | Email address to receive the digest |

4. Go to the **Actions** tab and confirm the workflow is enabled
5. Click **Run workflow** → set `debug_mode = true` → check the logs to verify

The workflow runs automatically at **7:00 AM UTC** every day. Edit the `cron` line in `.github/workflows/daily-digest.yml` to change the time.

## Cost estimate

With 3 topics × ~3 searches each, a typical run uses approximately:
- ~15,000 input tokens + ~1,500 output tokens per topic
- **~$0.02–0.05 per day** at current claude-sonnet-4-6 pricing

Brave Search free tier (2,000 queries/month) covers ~60+ runs/month with 3 topics.

## Troubleshooting

| Problem | Fix |
|---|---|
| `smtplib.SMTPAuthenticationError` | You used your Gmail password instead of an App Password. Generate one at myaccount.google.com/apppasswords |
| `requests.HTTPError: 429` from Brave | You've hit the free tier rate limit. Wait until the next month or upgrade your Brave plan |
| Workflow not running on schedule | GitHub Actions cron can be delayed up to 15–30 min. Use the manual "Run workflow" button to test immediately |
| `KeyError: 'ANTHROPIC_API_KEY'` | The secret name in GitHub doesn't match exactly — check for typos |
| Email lands in spam | Add the sender address to your contacts, or use a different Gmail account as sender |
