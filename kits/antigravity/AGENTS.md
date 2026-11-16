# Google Antigravity (Patched)

Google's Antigravity agent is available in this sandbox as `agy` with the QNIX
eligibility patch pre-baked. Run it from the shell or use it directly as your
primary coding agent.

Authentication has two modes and the sandbox picks between them for you: with
a Google credential bound, `GEMINI_API_KEY` carries a sentinel the egress
proxy swaps for the real key at Google's endpoints, and a startup hook sets
`modelProvider: gemini` in `~/.gemini/antigravity-cli/settings.json`. With
nothing bound, that key is removed and `agy` falls back to its interactive
Google sign-in.

Egress is governed by Docker Sandboxes network policy: outbound Internet access is open while local networks, private RFC 1918 subnets, and host services are blocked.
