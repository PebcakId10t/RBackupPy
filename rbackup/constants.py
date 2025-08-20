import os

# Default config dir
xdg_config = os.getenv('XDG_CONFIG_HOME') or os.path.join(os.getenv('HOME'), '.config')
g_default_config_path = os.path.join(xdg_config, "rbackup")

# Default config name
g_default_config_name = "rbackup"

# Default rclone remote
g_default_remote = "drive"

# Default log file
xdg_state = os.getenv('XDG_STATE_HOME') or os.path.join(os.getenv('HOME'), '.local', 'state')
g_default_log = os.path.join(xdg_state, "rbackup.log")

__all__= ["g_default_config_path",
          "g_default_config_name",
          "g_default_remote",
          "g_default_log"]
