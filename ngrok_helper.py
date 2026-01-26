"""Ngrok tunnel management for EcoPOOL web server."""
from typing import Optional, Tuple

_tunnel = None
_public_url = None


def start_tunnel(port: int, auth_token: Optional[str] = None) -> Tuple[bool, str]:
    """Start ngrok tunnel.

    Args:
        port: The local port to tunnel
        auth_token: Optional ngrok auth token for extended sessions

    Returns:
        Tuple of (success, public_url or error message)
    """
    global _tunnel, _public_url
    try:
        from pyngrok import ngrok, conf

        if auth_token:
            conf.get_default().auth_token = auth_token

        # Configure ngrok to skip browser warning
        _tunnel = ngrok.connect(
            port, 
            "http",
            options={"request_header.add": ["ngrok-skip-browser-warning: true"]}
        )
        _public_url = _tunnel.public_url
        return True, _public_url
    except ImportError:
        return False, "pyngrok not installed. Run: pip install pyngrok"
    except Exception as e:
        return False, str(e)


def stop_tunnel():
    """Stop the ngrok tunnel if running."""
    global _tunnel, _public_url
    try:
        from pyngrok import ngrok
        if _tunnel:
            ngrok.disconnect(_tunnel.public_url)
        ngrok.kill()
    except Exception:
        pass
    _tunnel = None
    _public_url = None


def get_public_url() -> Optional[str]:
    """Get the current public URL if tunnel is active.

    Returns:
        The public ngrok URL, or None if not active
    """
    return _public_url


def is_tunnel_active() -> bool:
    """Check if the ngrok tunnel is currently active.

    Returns:
        True if tunnel is active, False otherwise
    """
    return _tunnel is not None
