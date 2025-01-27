# V Rising Server Manager

V Rising Server Manager is an application for managing the V Rising game server. It provides a graphical interface for configuring FTP connections, editing configurations, managing shop products, tracking currency, and creating announcements.

## Installation

1. Ensure you have Python and the necessary libraries installed. You can install the dependencies using pip:

   ```bash
   pip install PyQt5 matplotlib
   ```

2. Download or clone the project repository.

3. Run the application:

   ```bash
   python V\ Rising.py
   ```

## Usage

### Tabs

- **FTP Connection**: Configure the connection to the FTP server for loading and saving configuration files.
- **Settings**: Edit the `BloodyRewards.cfg` configuration file.
- **Shop**: Manage the list of products in the shop.
- **Statistics**: Track player statistics and currency.
- **Announcements**: Create and edit announcements to be displayed in the game.

### Important Links

- Ensure you update the file paths on the FTP server in the code if they differ from the following:
  - Configuration: `/BepInEx/config/BloodyRewards.cfg`
  - Products: `/BepInEx/config/BloodyShop/products_list.json`
  - Announcements: `/BepInEx/config/KindredCommands/announcements.json`

### Known Issues

- **Settings Bug**: Occasionally, settings may change to `NONE`. To prevent data loss, it is recommended to save settings locally before making changes.
