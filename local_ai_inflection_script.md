**COLD OPEN**

Ten years ago, shipping an AI product meant negotiating AWS credits, provisioning GPU clusters, and writing a privacy policy that cost more than your first thousand users. Today, a $9 microcontroller can track a human heartbeat through drywall. A 99-million-parameter speech model on a laptop CPU outruns inference on an A100. And your entire personal AI agent stack fits in a local SQLite file with zero cloud dependencies. The local-first inflection point is here, and most of the industry hasn't noticed yet.

---

**BEAT 1 — Sensing the physical world without a camera**

RuView is a WiFi sensing platform that turns a commodity ESP32-S3 — a chip that costs nine dollars and draws so little power it can run on a phone charger — into a through-wall presence detector. It measures Channel State Information from standard WiFi signals, the same radio noise your router already floods your home with, and runs a 4-bit quantized model that fits in 8 kilobytes. That is smaller than most JPEG thumbnails. The accuracy numbers are legitimate: 100% for presence detection, reliable breathing rate and heart rate estimation through a standard interior wall at distances up to ten meters. On an M4 Pro it processes 164,000 embeddings per second, which means real-time multi-person tracking is computationally free on modern hardware. The entire stack runs on edge silicon — no cameras, no microphones, no cloud egress, no privacy liability. If you are building for elder care, security, or any environment where cameras are legally or socially unacceptable, this eliminates the trade-off between privacy and sensing. The pretrained model weights are on GitHub. The hardware BOM is under twenty dollars. There is no subscription.

[B-ROLL: ESP32-S3 board on a breadboard next to a WiFi router. Cut to a laptop screen showing a real-time spectrogram of CSI signal data with overlaid heartbeat waveform. Split-screen showing a person standing in one room and the detection UI on the other side of the wall.]

---

**BEAT 2 — On-device speech that refuses to sound robotic**

Supertonic 3 ships as a single `pip install` and gives you production-grade multilingual TTS in 31 languages from a 99-million-parameter model that runs on CPU faster than larger models run on an A100. It ships ten discrete expression tags — anger, whisper, cheer, breath, cry, fear, surprise, shout, sadness, and a laugh tag — so you can annotate SSML-like emotion markers in your text and get actual affective prosody on the other end. Independent benchmarks show it beats both ElevenLabs and OpenAI on complex text normalization — dates, addresses, abbreviations, heteronyms — which is the part of TTS that usually breaks silently in production. The package includes an HTTP server with an OpenAI-compatible endpoint, so you can point any existing TTS integration at `localhost` and get back speech. No GPU. No API key. No monthly minimum. The limitation worth noting: there is no voice cloning pipeline yet, so you are working from the shipped voice set. But for any application where voice selection is a design choice rather than a brand requirement, this removes the last excuse to keep TTS in the cloud.

[B-ROLL: Terminal window. `pip install supertonic` runs. Then `supertonic serve` starts the server. A `curl` command pipes generated speech into `afplay` and audio plays. Cut to a waveform editor showing the same sentence rendered with different expression tags — whisper versus cheer — and visibly different pitch contours.]

---

**BEAT 3 — A personal AI that lives on your disk**

OpenHuman is an open-source personal AI harness that connects 118 OAuth integrations — email, calendar, Slack, Discord, GitHub, Notion, Linear, and more — and auto-fetches your data every twenty minutes into a local Memory Tree stored in SQLite. It ships with an Obsidian vault integration so your notes become part of your agent's context automatically. TokenJuice, their compression layer, cuts LLM token costs by roughly 80% across a typical conversation window by deduplicating and intelligently summarizing context before it reaches the API call. All memory, all embeddings, all conversation history stays in a local SQLite database you own. OpenHuman is early — the beta has rough edges, the 118 integrations vary in stability, and you will probably file a bug report your first week — but the architecture is the right one for anyone who does not want their personal model to be a product. Separately, AI Engineering from Scratch is a 435-lesson free curriculum that starts at linear algebra and runs all the way to multi-agent swarms and MCP server design. Every lesson ships a reusable artifact — a prompt, a skill, an agent definition, an MCP server template — and there is a `/find-your-level` placement test so you skip the material you already know. If you have been feeling the gap between calling GPT APIs and actually understanding what is happening under the transformer, this is the bridge.

[B-ROLL: OpenHuman dashboard showing the Memory Tree as a force-directed graph, then a split-screen of an Obsidian vault with auto-synced notes. Cut to a terminal showing TokenJuice compression statistics — raw token count versus compressed count. Then scroll through the AI Engineering from Scratch curriculum page, pausing on a multi-agent swarm lesson with a code sample.]

---

**DEMO**

Here is the fastest way to confirm all of this is real. Open a terminal on any laptop made in the last five years, even in airplane mode.

```
pip install supertonic
supertonic serve
```

That is it. In under thirty seconds you have a local HTTP server listening on port 8000 that speaks 31 languages with affective prosody, no GPU required. Hit it with curl:

```
curl -X POST http://localhost:8000/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{"model": "supertonic-3", "input": "Your entire TTS stack just became a pip install.", "voice": "af_heart", "expression": "whisper"}' \
  --output demo.wav
```

Play that file. That is a zero-cloud, zero-API-key, zero-GPU TTS pipeline running on your hardware. If you have a Python application that already uses the OpenAI TTS SDK, change the base URL to `localhost:8000` and nothing else. It drops in as a replacement.

If you have Docker, you can also pull the RuView demo for through-wall sensing on simulated data:

```
docker pull ruvnet/wifi-densepose
docker run -p 3000:3000 ruvnet/wifi-densepose
```

Open `localhost:3000` and you will see real-time presence detection visualized over a simulated floor plan. The same architecture that runs on the ESP32 runs in that browser container. You can switch between presence, breathing, and heart-rate modes from the UI.

Two commands. Two working demos. Zero cloud. No credit card required.

[ON-SCREEN: Terminal window split into two sides. Left side: the `pip install supertonic && supertonic serve` sequence with a timer overlay. Right side: the `curl` command being typed and the resulting audio waveform appearing. Below: the Docker commands and the browser window showing the RuView visualization. All keystrokes visible, no cuts, no magic.]

---

**OUTRO**

The through-line across all four of these projects is the same: local-first AI is production-ready for a growing slice of the application stack. You trade the raw ceiling of frontier cloud models — massive context windows, fleet learning, trillion-parameter MoEs — for latency, privacy, zero operating cost, and the ability to ship without asking anyone for an API key. That trade gets better every quarter as quantization, architecture, and edge silicon improve. If you are starting something new today, pick one of these repos, clone it, and keep it local until you hit a wall that genuinely requires cloud-scale intelligence. You will be surprised how far you get. Go clone RuView, or Supertonic, or OpenHuman, and ship something this week that does not touch a single remote server. Each of these projects is MIT-licensed, actively maintained, and documented well enough that you can go from clone to working demo in under an hour. The only thing missing is your use case.
