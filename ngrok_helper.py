"""Ngrok tunnel management for EcoPOOL web server."""
import os
import tempfile
from typing import Optional, Tuple

_tunnel = None
_public_url = None
_config_file = None


def start_tunnel(port: int, auth_token: Optional[str] = None) -> Tuple[bool, str]:
    """Start ngrok tunnel.

    Args:
        port: The local port to tunnel
        auth_token: Optional ngrok auth token for extended sessions

    Returns:
        Tuple of (success, public_url or error message)
    """
    global _tunnel, _public_url, _config_file
    try:
        from pyngrok import ngrok, conf

        # Create a temporary ngrok config file to disable browser warning
        # This is the most reliable way to configure request headers
        config_content = f"""version: "2"
tunnels:
  ecopool:
    proto: http
    addr: {port}
    request_header:
      add:
        - "ngrok-skip-browser-warning: true"
"""
        
        # Create temporary config file
        config_fd, config_path = tempfile.mkstemp(suffix='.yml', prefix='ngrok_config_')
        try:
            with os.fdopen(config_fd, 'w') as f:
                f.write(config_content)
            
            _config_file = config_path
            
            # Configure pyngrok to use this config file
            # Preserve auth_token if provided
            pyngrok_config = conf.PyngrokConfig(
                config_path=config_path,
                auth_token=auth_token if auth_token else None
            )
            conf.set_default(pyngrok_config)
            
            # Connect using the named tunnel from config
            _tunnel = ngrok.connect(name="ecopool")
            _public_url = _tunnel.public_url
            return True, _public_url
        except Exception as config_error:
            # If config file approach fails, fall back to simple connection
            if os.path.exists(config_path):
                try:
                    os.unlink(config_path)
                except Exception:
                    pass
            _config_file = None
            # Fallback: try simple connection without warning bypass
            # Make sure auth_token is set for fallback too
            if auth_token:
                conf.get_default().auth_token = auth_token
            _tunnel = ngrok.connect(port, "http")
            _public_url = _tunnel.public_url
            return True, _public_url
    except ImportError:
        return False, "pyngrok not installed. Run: pip install pyngrok"
    except Exception as e:
        return False, str(e)


def stop_tunnel():
    """Stop the ngrok tunnel if running."""
    global _tunnel, _public_url, _config_file
    try:
        from pyngrok import ngrok
        if _tunnel:
            ngrok.disconnect(_tunnel.public_url)
        ngrok.kill()
    except Exception:
        pass
    _tunnel = None
    _public_url = None
    
    # Clean up temporary config file
    if _config_file and os.path.exists(_config_file):
        try:
            os.unlink(_config_file)
        except Exception:
            pass
    _config_file = None


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
