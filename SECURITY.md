Security

Never commit API keys, patent application documents, client information, or prosecution correspondence.

The original archive supplied for this upgrade contained a Gemini API key in .streamlit/secrets.toml. That file has been removed from this upgraded repository. Rotate/revoke the exposed key in Google AI Studio immediately and create a new secret locally or in GitHub/Streamlit Cloud secrets.

For production deployments, add authentication, encrypted storage, audit logging, retention controls, and per-user access control before processing confidential patent files.
