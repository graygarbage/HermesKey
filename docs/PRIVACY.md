# Privacy and network behavior

HermesKey performs speech recognition on the user's machine. It does not contain an analytics, tracking or transcript-upload endpoint. **Local inference is not the same as no network traffic**: setup and online model resolution have explicit network dependencies.

| Phase | Network use | Content sent by HermesKey |
| --- | --- | --- |
| Bootstrap/install | The standard `curl` command fetches the bootstrap script from GitHub, the release API selects a published archive, and pip installs speech dependencies from its configured package index (normally PyPI). Distro packages come from your distro's repositories. | No microphone audio or dictated text. The services see ordinary HTTP metadata such as IP address and requested package/release names. Review your package-index configuration if you changed it. |
| Online speech-model startup (`HERMESKEY_OFFLINE=0`, default) | `faster-whisper` / Hugging Face Hub can query model metadata **even if the model is cached**, and downloads model files if missing. A user-configured custom model source may have different behavior. | Model identifier, normal request metadata and IP address; HermesKey does not send audio/transcripts for inference. We cannot guarantee that every third-party model source has the same policies. |
| Strict offline speech-model startup (`HERMESKEY_OFFLINE=1`) | The speech process sets `HF_HUB_OFFLINE=1` before importing the model library, disables Hugging Face telemetry, and requests `local_files_only=True`. Missing cached/local models fail instead of downloading. | No intended model-resolution request. See the egress test recommendation below; a local configuration cannot control unrelated applications on your desktop. |
| Recording and transcription | Microphone audio is captured into a private user-runtime file, sent through a private Unix socket to the local prewarmed model, then deleted by default. | No audio or transcript is sent to a remote inference API by HermesKey. `KEEP_AUDIO=1` intentionally retains the last recording for debugging. |
| Insertion and support | Text is typed into the focused app or copied to the local clipboard according to your preferences. Diagnostic logs are local-only and no support bundle is automatically uploaded. | `COPY_TO_CLIPBOARD=1` (default) can leave transcripts in desktop clipboard history or a third-party clipboard sync tool. Review logs before sharing them; see [#63](https://github.com/graygarbage/HermesKey/issues/63) and [#67](https://github.com/graygarbage/HermesKey/issues/67). |

For fewer local copies, use **Privacy-first typing** in Settings → Input. This explicitly chooses `INSERT_MODE=type` with `COPY_TO_CLIPBOARD=0`; it does not erase existing KDE clipboard history. This preference makes `ydotool` Unicode paste unavailable, so unsupported non-ASCII text is refused with a notification. Clipboard-only mode remains an explicit request to copy even when backup is off. HermesKey cannot control other desktop clipboard managers or synchronization services.

## Choosing strict offline speech startup

First explicitly download the model in normal mode (or select a local model path), then turn on **Strict offline speech model** in Settings → Speech or set `HERMESKEY_OFFLINE=1` in `~/.config/hermeskey/hermeskey.env`. Restart `hermeskey.service` when prompted. If the model is not available locally, the service **fails without fetching it**; disable offline mode to acquire it with consent, or install the model locally. `hermeskey-doctor --config-only` validates the flag. Strict offline speech startup does **not** make the bootstrap installer, system packages, pip or unrelated desktop applications offline.

To verify on your own machine, preload a model, restart the service with `HERMESKEY_OFFLINE=1` while outbound network access is blocked, then transcribe the bundled synthetic test clip. Keep network access blocked for repeated service restarts as well as dictation. Do not use personal recordings or paste their transcripts into an issue. Tests in the repository mock the model downloader; real egress verification is still necessary on supported desktops.

## Future local translation

Translation is not a HermesKey feature yet. If implemented, it should use a **local LLM/model by default**, with no remote inference fallback, transcript/prompt telemetry or content logs. Model acquisition must be explicit and separate from offline use. Test translations after a preloaded model with network egress blocked, and explain any new network/data flow before shipping it.
