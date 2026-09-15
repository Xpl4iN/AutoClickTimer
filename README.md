# AutoClick Timer

AutoClick Timer is a modern, responsive automation utility built with Python and CustomTkinter. It allows you to queue up multiple keyboard and mouse clicks sequentially, set custom wait timers, and even trigger automated Windows sleep and wake schedules (with Remote Desktop unlock support).

## Features

- **Modern UI:** Responsive dark Material Design theme using CustomTkinter and a custom teal color palette.
- **Multiple Actions Queue:** Build a sequence of actions including Enter presses, left clicks, text prompts, and sleep-and-wake tasks.
- **Dynamic Presets:** Click-and-go time presets (e.g., 15m, 30m, 1h, 2h, 3h, 4h, 5h, 6h, 8h, 10h, 12h, 24h) that calculate target clock times dynamically.
- **Combo Presets:** One-click scheduling for common combinations like *Sleep & Wake + Enter*.
- **Responsive Layout:** Stacks panels vertically to run as a slim sidebar window (down to 380px width) or side-by-side as a wide dashboard.
- **Sleep & Wake Automation:** Automatically configures Windows RTC wake timers, disables unattended sleep timeouts, registers a SYSTEM-level scheduled task to wake and unlock your session, and suspends the PC.
- **Power and Lid Controls:** Configure lid-close and power-button behavior independently for plugged-in and battery use, plus display timeout settings for remote access workflows.
- **Idle Sleep Controls:** Configure the Windows idle-sleep timeout independently for plugged-in and battery use, including Never and long-running remote-work options.
- **CLI and MCP Control:** Control a running instance through the authenticated loopback control bridge. Every remote action is written to the in-app log with its source.
- **Explicit Emergency Stop:** Stops the active queue with the UI Stop button or Ctrl+Shift+F12. Moving the pointer to the top-left corner is ignored so RustDesk reconnects cannot trigger a false stop.

## Requirements

The app requires administrative privileges on startup to configure scheduled tasks and power settings for the sleep & wake action.

### Dependencies
If running from source, the application will automatically prompt and install required libraries:
- `customtkinter`
- `pyautogui`
- `pyperclip`
- `Pillow`

## Building from Source

To compile the script into a single, standalone `.exe` file, run PyInstaller using the provided spec file:
```bash
pyinstaller --clean AutoClickTimer.spec
```
The compiled binary will be generated in the `dist/` directory.

## Remote control

Start the GUI normally. From a PowerShell window on the same laptop, use the CLI to inspect or change the queue:

```powershell
python autoclicktimer.py --cli status
python autoclicktimer.py --cli add --action sleep --after 3600 --pre-sleep-grace 10 --post-wake-delay 30
python autoclicktimer.py --cli schedule-enter --after 3660
python autoclicktimer.py --cli power set --ac-sleep 0 --battery-sleep 30
```

The control endpoint is loopback-only and uses a per-run token stored in the user's local application data. The same endpoint exposes the small JSON-RPC MCP bridge at `/mcp`. For stdio-based MCP clients, configure `python autoclicktimer.py --mcp`. MCP and CLI commands are applied on the UI thread and appear in the Log panel.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
