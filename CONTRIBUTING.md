# Contributing

1. Fork, branch, keep changes focused.
2. Sender: `cd sender`, create a venv, `pip install -r requirements.txt`, `python -m pytest tests`.
3. Receiver: `cd receiver && gradlew assembleDebug testDebugUnitTest`.
4. Protocol changes must update `shared/protocol/PROTOCOL.md`, both implementations and `shared/test-data/`.
5. In your pull request, say what you tested and on which hardware.
