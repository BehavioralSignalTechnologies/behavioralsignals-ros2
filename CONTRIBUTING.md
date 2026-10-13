# Contributing

Thanks for helping improve the Behavioral Signals ROS 2 integration. By taking part, you agree to
follow our [Code of Conduct](CODE_OF_CONDUCT.md).

## Report a bug or ask for a feature

Open an [issue](https://github.com/BehavioralSignalTechnologies/behavioralsignals-ros2/issues/new/choose).
Never paste your API key or CID in an issue.

To report a security problem, follow [SECURITY.md](SECURITY.md) instead.

## Tests

The tests need no credentials and no network. Run them with Docker:

```
docker build -t behavioralsignals-ros2 -f docker/Dockerfile .
docker run --rm behavioralsignals-ros2
```

CI runs the same two commands on every pull request.

## Using an AI assistant

[AGENTS.md](AGENTS.md) has setup steps and rules for coding agents.

## Pull requests

1. Create a branch from `main`.
2. Keep each pull request to one change.
3. If you change how the nodes are used, update `README.md` and `docs/`.
4. Open the pull request and fill in the template.
