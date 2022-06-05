Blankie
=======

*Blankie* is a stand-alone daemon which manages screen locking and power management for DYI desktop environments (such as using i3).

For example, it can be configured to do the following:

- If there is no input (keyboard/mouse) for ten minutes, gently fade the screen to black over a minute, then turn the screen off and run a screen locker (such as i3lock).
- If the system is on battery power, suspend it instead of just turning the screen off.
- Use lower timeouts while the screen is locked.
- Disable notification popups, TTY switching, and USB storage hot-plugging while the screen is locked.

Notable features:

- Support for multiple sessions (e.g. multiple X instances on different terminals).
- Partial support for Linux console sessions.
- Modular and extensible architecture.
- Configuration with unlimited flexibility (the configuration is a user-supplied Python function).
- Stand-alone - does not depend on a desktop environment such as GNOME or KDE.
- Efficient event-driven architecture - does not poll and does not use wasteful timers, saving battery life.

Blankie started out as a project to replace the now-abandoned xss-lock program, but grew into an effort of implementing a correct and reliable solution for this problem space.


Status
------

This project is in alpha. Please try it and file bug reports!

Feature suggestions are also welcome.

Roadmap:

- General polishing.
- DBus integration module for logind.
- DBus integration module for the session screen saver protocol.
- "Caffeinate" command.
- Back-off logic (increase timeout if system became unidle shortly after the idle action).
- Integrate the `xss` program into Blankie.
- Integrate the `xbacklight` program into Blankie.
- Improve TTY locking. (Need to fork physlock and include a small setuid program with Blankie.)
- Troubleshooting tool (why is the screen saver not starting).

Usage
-----

The recommended way to run Blankie is with a systemd user unit.

Create `~/.config/systemd/blankie.service`:

```
[Service]
Type=forking
ExecStart=%h/path/to/blankie
PIDFile=$XDG_RUNTIME_DIR/blankie/daemon.pid

[Install]
WantedBy=default.target
```

Then, run `systemctl --user enable --now blankie`.

To make `blankie` manage your X sessions, add to your `~/.xinitrc`:

```
path/to/blankie attach
```

To make `blankie` also manage your TTY sessions (experimental), add to your `~/.bashrc`:

```
if [[ ! -v DISPLAY && "$(tty)" == /dev/tty* ]] ; then
    path/to/blankie attach
fi
```


Configuration
-------------

Create `~/.config/blankie/config.py`.

A minimal configuration can look as follows:

```python
import blankie

def config(c):
    c.on_idle(15 * 60, 'lock')
    c.on_lock('i3lock')
```

As a reference, the author's personal configuration can be found [here](https://gist.github.com/CyberShadow/aaacbd456efa6e4b6886d453beea9a86).
