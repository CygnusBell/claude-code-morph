"""Configuration settings for Claude Code Morph."""

import os
from pathlib import Path
from typing import Dict, Any, Optional

class MorphConfig:
    """Application configuration manager."""
    
    # Default configuration values
    DEFAULTS = {
        # UI Settings
        "theme": "dark",
        "auto_save_workspace": True,
        "hot_reload_enabled": True,
        "startup_workspace": "default.yaml",
        
        # Claude CLI Settings
        "claude_auto_start": True,
        "claude_command": ["claude", "code"],
        "claude_env": {},
        
        # Prompt Optimizer Settings
        "optimizer_enabled": True,
        "optimizer_model": "llama-4-maverick-17Bx128E",  # Groq model
        "optimizer_api": "groq",  # Using Groq API
        
        # Panel Settings
        "panel_border_style": "solid",
        "panel_border_color": "blue",
        
        # Terminal Settings
        "terminal_rows": 40,
        "terminal_cols": 120,
        "terminal_scrollback": 10000,
        
        # Development Settings
        "debug_mode": False,
        "log_level": "INFO",
    }
    
    def __init__(self, config_path: Optional[Path] = None):
        """Initialize configuration.
        
        Args:
            config_path: Path to configuration file
        """
        self.config_path = config_path or Path.home() / ".claude-code-morph" / "config.yaml"
        self.config: Dict[str, Any] = self.DEFAULTS.copy()
        self._load_config()
        self._load_env_overrides()
        
    def _load_config(self) -> None:
        """Load configuration from file if it exists."""
        if self.config_path.exists():
            try:
                import yaml
                with open(self.config_path, 'r') as f:
                    user_config = yaml.safe_load(f) or {}
                    self.config.update(user_config)
            except Exception as e:
                print(f"Warning: Failed to load config from {self.config_path}: {e}")
                
    def _load_env_overrides(self) -> None:
        """Load configuration overrides from environment variables."""
        # Map of env var names to config keys
        env_mapping = {
            "CCM_THEME": "theme",
            "CCM_AUTO_SAVE": "auto_save_workspace",
            "CCM_HOT_RELOAD": "hot_reload_enabled",
            "CCM_STARTUP_WORKSPACE": "startup_workspace",
            "CCM_CLAUDE_AUTO_START": "claude_auto_start",
            "CCM_OPTIMIZER_ENABLED": "optimizer_enabled",
            "CCM_OPTIMIZER_MODEL": "optimizer_model",
            "CCM_OPTIMIZER_API": "optimizer_api",
            "CCM_DEBUG": "debug_mode",
            "CCM_LOG_LEVEL": "log_level",
        }
        
        for env_var, config_key in env_mapping.items():
            value = os.getenv(env_var)
            if value is not None:
                # Convert boolean strings
                if value.lower() in ("true", "false"):
                    value = value.lower() == "true"
                self.config[config_key] = value
                
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value.
        
        Args:
            key: Configuration key
            default: Default value if key not found
            
        Returns:
            Configuration value
        """
        return self.config.get(key, default)
        
    def set(self, key: str, value: Any) -> None:
        """Set configuration value.
        
        Args:
            key: Configuration key
            value: Configuration value
        """
        self.config[key] = value
        
    def save(self) -> None:
        """Save configuration to file."""
        try:
            import yaml
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.config_path, 'w') as f:
                yaml.dump(self.config, f, default_flow_style=False)
        except Exception as e:
            print(f"Error saving config: {e}")
            
    def get_api_key(self, service: str) -> Optional[str]:
        """Get API key for a service.
        
        Args:
            service: Service name ("groq", "anthropic" or "openai")
            
        Returns:
            API key if available
        """
        if service == "groq":
            return os.getenv("GROQ_API_KEY")
        elif service == "anthropic":
            return os.getenv("ANTHROPIC_API_KEY")
        elif service == "openai":
            return os.getenv("OPENAI_API_KEY")
        return None
        
    def validate(self) -> bool:
        """Validate configuration.
        
        Returns:
            True if configuration is valid
        """
        # Check if optimizer is enabled but no API key is available
        if self.get("optimizer_enabled"):
            api = self.get("optimizer_api")
            if not self.get_api_key(api):
                print(f"Warning: Optimizer enabled but no {api.upper()}_API_KEY found")
                
        return True

# Global configuration instance
config = MorphConfig()

# Convenience functions
def get_config(key: str, default: Any = None) -> Any:
    """Get configuration value."""
    return config.get(key, default)
    
def set_config(key: str, value: Any) -> None:
    """Set configuration value."""
    config.set(key, value)
    
def save_config() -> None:
    """Save configuration."""
    config.save()