# Automated Multi-Platform Posting

A FastAPI service that takes one short message with a call-to-action (CTA) link and publishes it to six platforms at the same time. If one platform fails, the others still post, and the response reports the outcome per platform.

## Platforms

| Platform | API used | Credentials needed |
|---|---|---|
| **Telegraph** | `api.telegra.ph` `createAccount` / `createPage` | None (an anonymous account is created automatically) |
| **Mastodon** | `POST /api/v1/statuses` | Access token with `write:statuses` |
| **Bluesky** | AT Protocol `createSession` / `createRecord` | Handle and app password |
| **Dev.to** | `POST /api/articles` | API key |
| **GitHub Gist** | `POST /gists` (public gist) | Token with the `gist` scope |
| **Telegram** | Bot API `sendMessage` to a public channel | Bot token and channel username |

A platform with no credentials is reported as `failed` with a "Missing credentials" error. The rest still run, so the service works with any subset configured.

No LLM platform is included: the major LLM providers expose no public API for publishing a post, only for generating text.

## Setup

Requires Python 3.10 or newer.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Fill in the values you have in `.env`. Never commit `.env`; it is listed in `.gitignore`.

### Getting credentials

| Variable | Where to get it |
|---|---|
| `TELEGRAPH_TOKEN` | Optional. Leave empty to use a new anonymous account on every request. |
| `MASTODON_INSTANCE` | Your server, default `https://mastodon.social`. |
| `MASTODON_ACCESS_TOKEN` | Preferences, Development, New application. Tick `write:statuses`, then copy "Your access token". |
| `BLUESKY_HANDLE` | Your handle, for example `you.bsky.social`. |
| `BLUESKY_APP_PASSWORD` | Settings, Privacy and security, App passwords. Use an app password, not your account password. |
| `DEVTO_API_KEY` | Settings, Extensions, Generate API key. |
| `GITHUB_TOKEN` | Settings, Developer settings, Personal access tokens. Give it the `gist` scope only. |
| `TELEGRAM_BOT_TOKEN` | Message `@BotFather`, send `/newbot`, copy the token. |
| `TELEGRAM_CHAT_ID` | A public channel such as `@my_channel`, with the bot added as an administrator. |
| `REQUEST_TIMEOUT` | Seconds to wait for each platform. Default 20. |

## Run

```bash
uvicorn app.main:app --host 0.0.0.0 --port 4000
```

Interactive API documentation: http://localhost:4000/docs

## API

`POST http://localhost:4000/posting`

### Request

```json
{
  "message": "Check out our latest business platform and grow your online visibility. https://example.com"
}
```

```bash
curl -X POST http://localhost:4000/posting \
  -H "Content-Type: application/json" \
  -d '{"message": "Check out our latest business platform and grow your online visibility. https://example.com"}'
```

### Validation rules

- The message must not be empty.
- The message must not exceed 200 characters.
- The message must contain exactly one link.
- The link must be a full `http://` or `https://` URL with a real domain.

### Response (200)

The status code is 200 whenever the request was valid, even if some or all platforms failed. Look at each result for the outcome. `success` is `true` when at least one platform posted.

The values below show the response format.

```json
{
  "success": true,
  "results": [
    {
      "platform": "Telegraph",
      "status": "success",
      "posted_url": "https://telegra.ph/Check-out-our-latest-business-11-15",
      "public_access": true,
      "date": "2026-11-15",
      "time": "10:30:00",
      "error": null
    },
    {
      "platform": "Mastodon",
      "status": "failed",
      "posted_url": null,
      "public_access": false,
      "date": null,
      "time": null,
      "error": "Missing credentials: set MASTODON_ACCESS_TOKEN"
    }
  ]
}
```

| Field | Meaning |
|---|---|
| `platform` | Platform name |
| `status` | `success` or `failed` |
| `posted_url` | Link to the published post, `null` on failure |
| `public_access` | `true` if a GET request to `posted_url` returns 200 |
| `date`, `time` | When the post was made, `null` on failure |
| `error` | What went wrong, `null` on success |

### Validation error (422)

```bash
curl -X POST http://localhost:4000/posting \
  -H "Content-Type: application/json" \
  -d '{"message": "No link in this message"}'
```

```json
{
  "success": false,
  "errors": [
    {
      "field": "message",
      "message": "Message must contain exactly one CTA link (found 0)."
    }
  ]
}
```

## Tests

```bash
pytest
```

The tests use fake HTTP transports, so they need no network and no credentials. The project was built test-first.

## Project structure

```
app/
  main.py                  FastAPI app and POST /posting
  schemas.py               Request validation and response models
  config.py                Reads settings from the environment
  platforms/
    base.py                Platform interface and shared error handling
    registry.py            The list of platforms used by the app
    telegraph.py  mastodon.py  bluesky.py  devto.py  gist.py  telegram.py
  services/
    posting_service.py     Runs all platforms concurrently and collects results
tests/                     One test file per module, plus end-to-end tests
.env.example               Template for credentials (no real secrets)
```

## Design notes

- **Concurrent posting.** All platforms run at once with `asyncio.gather`, so total time is about the slowest platform, not the sum.
- **Independent failures.** Every platform's exception is caught and turned into a `failed` result. One failure never stops the others.
- **Real public check.** `public_access` comes from fetching the posted URL, not from assuming it.
- **Adding a platform.** Create a class in `app/platforms/` that extends `Platform`, then add it to `all_platforms()` in `registry.py`.
