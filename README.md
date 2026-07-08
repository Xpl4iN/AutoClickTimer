# AutoClick Timer

AutoClick Timer is a modern, responsive automation utility built with Python and CustomTkinter. It allows you to queue up multiple keyboard and mouse clicks sequentially, set custom wait timers, and even trigger automated Windows sleep and wake schedules (with Remote Desktop unlock support).

## Features

- **Modern UI:** Responsive dark Material Design theme using CustomTkinter and a custom teal color palette.
- **Multiple Actions Queue:** Build a sequence of actions including Enter presses, left clicks, text prompts, and sleep-and-wake tasks.
- **Dynamic Presets:** Click-and-go time presets (e.g., 15m, 30m, 1h, 2h, 3h, 4h, 5h, 6h, 8h, 10h, 12h, 24h) that calculate target clock times dynamically.
- **Combo Presets:** One-click scheduling for common combinations like *Sleep & Wake + Enter*.
- **Responsive Layout:** Stacks panels vertically to run as a slim sidebar window (down to 380px width) or side-by-side as a wide dashboard.
- **Sleep & Wake Automation:** Automatically configures Windows RTC wake timers, disables unattended sleep timeouts, registers a SYSTEM-level scheduled task to wake and unlock your session, and suspends the PC.
- **Emergency Failsafe:** Instantly stops the active queue by moving your mouse cursor to the top-left corner of the monitor screen (coordinate 0,0).

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

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
