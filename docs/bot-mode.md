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
- explicit mentions select the Bots that start the run, while no Bot mention
  selects the whole room;
- `PASS`, `(pass)`, empty replies, failures, timeouts, and repeated normalized
  replies from the same Bot within one user send stay hidden; identical replies
  from different Bots or later user sends remain visible;
- a fully silent round settles the run;
- an explicitly mentioned Bot starts alone, but its own explicit mention of a
  peer is a bounded handoff that can pull that peer into the next round;
- a whole-room request gives every member one standalone turn; room @mentions
  are removed from those replies so redundant tags cannot create a noisy second
  round;
- `@user` marks the room as needing human judgment;
- each member receives only unseen room deltas through a per-member/thread watermark;
- new input increments a cancellation epoch, preventing stale replies from landing;
- attempts and failures remain truthful in a private activity feed;
- local attachments are copied into each receiving profile instead of sharing filesystem paths;
- remote attachments are transferred one at a time over the authenticated peer API, decoded strictly, and staged under the receiving profile with private permissions. Remote files are capped at 7 MiB so the Base64 envelope remains below the API server's 10 MB request limit; local files retain the 25 MiB limit.

Room state is stored in profile-root-aware `bot_rooms.json`. Each local member uses its own persistent `Group: <name>` canonical session. Bot identities are durable across profile renames, and active Kanban/tool-worker sessions appear in the roster without turning ordinary sessions into Bot Chats.

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

### Normal-chat Telegram room bindings

A Telegram controller can bind one authorized group directly to a Bot Room so
ordinary non-command messages enter the room without `/botroom` or an
`@controller` trigger:

```yaml
telegram:
  allowed_chats: ["-1001234567890"]
  group_allowed_chats: ["-1001234567890"]
  require_mention: true
  exclusive_bot_mentions: true
  bot_room_bindings:
    "-1001234567890":
      room_id: room-0123456789ab
      controller_handle: clio
      delivery: profile_bots  # optional: post each reply from its profile Bot account
      profile_bot_usernames:  # optional: internal room handle -> Telegram username
        clio: ClioloopControllerBot
        viktorian: ClioloopViktorianBot
      render_profile_bot_mentions: true  # optional: make outbound @handles clickable
      show_tool_progress: true           # optional: post compact tool-name updates
      turn_timeout_seconds: 1800         # optional: 30–3600; default 300
```

The binding is routing only and never bypasses user authorization, chat/topic
allowlists, or ignored threads. Exclusive mentions of other Telegram bots stay
blocked unless that public username is explicitly mapped to an internal room
handle by `profile_bot_usernames` in this exact binding. Commands addressed to
another Bot remain excluded. Telegram must still deliver plain group messages
to the controller: make that controller a group administrator or disable its
BotFather Privacy Mode.
Other Telegram bot accounts should remain mention-gated. When
`delivery: profile_bots` is enabled, every local room member Bot must also be a
member of the Telegram group; it does not need administrator access or disabled
Privacy Mode merely to send its own replies.

If a profile Bot also runs its own Telegram gateway, exclude the
controller-managed group in that profile so the same user message is not
processed once independently and once through the Council:

```yaml
telegram:
  ignored_chats: ["-1001234567890"]
```

This blocks only that profile gateway's group ingestion; DMs remain available,
and the controller can still deliver Council replies through the profile's Bot
token.

For a bound group:

- plain text with no internal room handle selects the whole room;
- an internal handle such as `@viktorian` selects only that profile for one
  initial turn; if that Bot explicitly mentions a peer, the peer can continue
  the bounded handoff in the next round;
- a configured public Telegram username such as `@ClioloopViktorianBot` is
  canonicalized to its internal handle before room selection, so mentioning one
  profile account still starts with only that profile;
- an exact mention of the controller Telegram username selects
  `controller_handle` when configured;
- multiple internal handles retain bounded cross-review and handoffs;
- commands continue through the ordinary gateway command path;
- supported cached images, PDF, plain-text, and Markdown attachments are copied
  into recipient profiles through the existing room attachment safeguards.

Model reasoning remains enabled for inference and stored for valid provider
replay, but reasoning presentation is always hidden in shared
`group`/`forum`/`channel` chats. A profile may still display reasoning in its DMs
when configured to do so.

When `show_tool_progress: true`, each local profile Bot posts compact live
updates from its own Telegram account, for example `🛠 Using tool: search_files`.
Only validated tool names and failure state cross the child boundary—arguments,
results, filesystem contents, credentials, and reasoning never enter these
progress messages. Tool activity is also retained in the room's private
activity feed. `turn_timeout_seconds` raises the per-Bot wall-clock ceiling for
long maintenance or delegated work; it is binding-local, accepts 30–3600
seconds, and does not weaken epoch supersession or cancellation.

Local Bot children return their final reply over a private token-bound result
file rather than captured terminal stdout. This keeps tool/status presentation
separate from the authoritative response and prevents valid answers from being
misclassified as `PASS`.

With `delivery: profile_bots`, internal cross-review still completes through the
controller's profile-backed room, but each finalized visible reply is sent in
room order using the author's profile-scoped Telegram token. The controller
posts no duplicate aggregate message. If a profile account cannot deliver, the
controller emits only a generic failure notice and never impersonates that Bot.
When `render_profile_bot_mentions: true`, internal mentions in the outbound copy
are replaced with their configured Telegram usernames so they are clickable;
the canonical room transcript and handoff routing remain internal-handle based.

`profile_bot_usernames` contains public routing metadata only—never Bot tokens.
The mapping is not queried from Telegram at message time and must be updated if
a BotFather username or internal room handle changes. Invalid or ambiguous maps
fail closed rather than turning a direct mention into a whole-room request.

Use one room ID per Telegram group unless sharing a transcript is intentional.
Telegram never delivers messages authored by one bot account to another, so
cross-review always happens through the controller's profile-backed room rather
than through Telegram bot-to-bot traffic. Without `delivery: profile_bots`, the
legacy controller-attributed aggregate reply remains the default.

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
- `POST /api/bots/{profile}/attachments` (peer-only staged attachment transfer)
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
