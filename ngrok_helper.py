"""Ngrok tunnel management for EcoPOOL web server."""
import os
import sys
import atexit
import signal
import tempfile
from typing import Optional, Tuple

_tunnel = None
_public_url = None
_config_file = None
_cleanup_registered = False
_original_sigint = None
_original_sigterm = None


def _cleanup_on_exit():
    """Cleanup handler called on program exit."""
    stop_tunnel()


def _signal_handler(signum, frame):
    """Handle SIGINT/SIGTERM for clean shutdown."""
    stop_tunnel()
    # Call original handler if it exists
    if signum == signal.SIGINT and _original_sigint:
        if callable(_original_sigint):
            _original_sigint(signum, frame)
        elif _original_sigint == signal.SIG_DFL:
            sys.exit(0)
    elif signum == signal.SIGTERM and _original_sigterm:
        if callable(_original_sigterm):
            _original_sigterm(signum, frame)
        elif _original_sigterm == signal.SIG_DFL:
            sys.exit(0)


def start_tunnel(port: int, auth_token: Optional[str] = None,
                 static_domain: Optional[str] = None) -> Tuple[bool, str]:
    """Start ngrok tunnel.

    Args:
        port: The local port to tunnel
        auth_token: Optional ngrok auth token for extended sessions
        static_domain: Optional static domain (e.g., 'myapp.ngrok-free.app')
                      Using a static domain eliminates the browser warning completely.

    Returns:
        Tuple of (success, public_url or error message)
    """
    global _tunnel, _public_url, _config_file, _cleanup_registered
    global _original_sigint, _original_sigterm

    # Register cleanup handlers on first use
    if not _cleanup_registered:
        atexit.register(_cleanup_on_exit)

        # Register signal handlers for clean shutdown (Windows-safe)
        try:
            _original_sigint = signal.signal(signal.SIGINT, _signal_handler)
        except (ValueError, OSError):
            pass  # Signal handling not available in this context

        try:
            # SIGTERM not available on Windows
            if hasattr(signal, 'SIGTERM'):
                _original_sigterm = signal.signal(signal.SIGTERM, _signal_handler)
        except (ValueError, OSError):
            pass

        _cleanup_registered = True

    try:
        from pyngrok import ngrok, conf

        # Clean up static domain format if provided
        if static_domain:
            static_domain = static_domain.strip()
            if static_domain.startswith('https://'):
                static_domain = static_domain[8:]
            elif static_domain.startswith('http://'):
                static_domain = static_domain[7:]
            # Remove any trailing slashes or paths
            static_domain = static_domain.split('/')[0]

            # Validate domain format
            if not static_domain or '.' not in static_domain:
                return False, "Invalid static domain format. Expected: yourname.ngrok-free.app"

            # Auth token required for static domains
            if not auth_token:
                return False, "Auth token is required when using a static domain"

        # Create ngrok config file - works for both static domain and regular tunnels
        # Using config file is more reliable than passing parameters directly
        if static_domain:
            # Config with static domain (eliminates browser warning completely)
            config_content = f"""version: "2"
tunnels:
  ecopool:
    proto: http
    addr: {port}
    domain: {static_domain}
"""
        else:
            # Config without static domain - use header to reduce warning
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

            # Debug: Print what URL we got vs what we expected
            if static_domain:
                print(f"[ngrok] Requested domain: {static_domain}")
                print(f"[ngrok] Got URL: {_public_url}")
                # Verify the domain matches
                if static_domain not in _public_url:
                    print(f"[ngrok] WARNING: Domain mismatch! Check your ngrok dashboard.")

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
