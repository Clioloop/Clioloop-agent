# Clio Bot Mode

Clio Bot Mode turns existing isolated profiles into durable named Bots. It is a Clio subsystem built on profile metadata, SQLite sessions, cron, the authenticated API server, and the existing CLI/gateway runtime.

## Identity and isolation

- A Bot is a Clio profile; no second agent database is introduced.
- `profile.yaml` may contain optional `bot` presentation metadata.
- `SOUL.md`, credentials, memory, skills, tools, MCP configuration, sessions, and cron remain profile-scoped.
- Profiles without Bot metadata remain compatible and appear as Bots by default. Set `bot.enabled: false` to exclude one.
- Canonical Bot Chats are hidden, pinned sessions identified by `canonical_key=bot.chat`; their mutable title is not their identity.

## CLI

```bash
clio bot list
clio bot show PROFILE
clio bot set PROFILE --display-name "Research" --title "Primary researcher"
clio bot chat PROFILE
clio bot dm TARGET --from SENDER --file /path/to/message.txt

clio group create "Launch review" researcher reviewer
clio group list
clio group send ROOM_ID --file /path/to/request.txt

clio routine add PROFILE "Daily review" "0 9 * * *" --file prompt.txt

clio peer add laptop https://host.example --key '...'
clio peer roster
clio peer dm laptop/researcher --from reviewer --file message.txt
```

Use `--file` for Bot-authored or untrusted text. The message is passed through an argv list and a mode-0600 temporary file; it is never interpolated into a shell command.

`clio chat --query-file PATH` is also available, with `-` for stdin. It is mutually exclusive with `-q` and rejects empty, NUL-containing, or oversized input.

## Bounded rooms

Rooms enforce:

- 2–6 distinct Bots;
- serial turns;
- at most 3 rounds;
- at most 10 visible Bot messages per user send;
- explicit mentions select eligible Bots, while no Bot mention selects the whole room;
- `PASS`, `(pass)`, empty replies, duplicates, failures, and timeouts stay hidden;
- a fully silent round settles the run;
- Bot mentions can pull members into the next round;
- `@user` marks the room as needing human judgment;
- each member receives only unseen room deltas through a per-member/thread watermark;
- new input increments a cancellation epoch, preventing stale replies from landing;
- attempts and failures remain truthful in a private activity feed;
- attachments are copied into each receiving profile rather than sharing another profile's filesystem path.

Room state is stored in profile-root-aware `bot_rooms.json`. Each local member uses its own persistent `Group: <name>` canonical session.

## Messaging gateways

Gateway commands:

```text
/bots
/botroom list
/botroom create Launch review | researcher,reviewer
/botroom show ROOM_ID
/botroom send ROOM_ID | Review the launch plan and call out blockers.
/botroom delete ROOM_ID
```

`/botroom send` runs one bounded orchestration and posts attributed visible replies. It avoids the noisy pattern where independent Telegram Bots all react to every group message.

## Desktop/TUI RPC

The TUI gateway exposes:

- `bot.list`, `bot.get`, `bot.dm`
- `bot.rooms.list`, `bot.rooms.create`, `bot.rooms.get`, `bot.rooms.send`, `bot.rooms.delete`

These methods let Desktop render a roster and room UI without owning Bot state.

## Authenticated HTTP API

When the API Server platform is enabled:

- `GET /api/bots`
- `GET /api/bots/{profile}`
- `POST /api/bots/{profile}/dm`
- `GET|POST /api/bot-rooms`
- `GET|DELETE /api/bot-rooms/{room_id}`
- `POST /api/bot-rooms/{room_id}/messages`

The endpoints use the API server's existing bearer authentication. Peer URLs are ordinary configuration; peer keys are stored separately in the profile `.env`.

`clio peer roster [PEER ...]` authenticates to each selected connection's `GET /api/bots`, merges it with the local roster, and source-qualifies handles when the same profile name exists on more than one gateway. An unreachable peer is reported in the JSON `errors` object while healthy sources remain usable; peer credentials are never included in roster output.

## Canonical prompt behavior

Only a canonical Bot Chat receives the teammate protocol. A capability fingerprint covers Bot metadata, roster, SOUL, skills, toolsets, MCP servers, and peers. The stable prompt refreshes when that fingerprint changes; ordinary sessions and user-authored `SOUL.md` are not modified.

`agent.bot_mode_protocol: false` disables protocol injection without deleting Bot state.

## Migrations and rollback

The additive state migration introduces canonical owner metadata and a partial unique index. Existing sessions remain ordinary visible sessions. Older clients ignore the extra columns.

Operational rollback is non-destructive:

1. Disable `agent.bot_mode_protocol`.
2. Stop using `/botroom` or the Bot RPC/API endpoints.
3. Leave canonical sessions and room state in place for later re-enablement.

Do not manually remove migrated columns from `state.db`.
