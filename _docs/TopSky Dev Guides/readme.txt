The folders "CursorsBlack" and "CursorsWhite" contain plugin cursors in both black and white color. Other than the colors being reversed, the cursors in the two folders are identical. The default cursors in the root folder of the package are the black ones. The plugin will use whichever cursors it finds in the same folder as the plugin dll (all cursor types must be found, if even one is not present the plugin custom cursors will not be used).

The folders "Settings - Setup A" and "Settings - Setup B (COOPANS)" contain EuroScope settings files:
- Lists.txt (EuroScope default list definitions)
- Plugins.txt (plugin custom list definitions)
- Tags.txt (an example tag setup)

The files can be used as-is, or as a starting point for creating your own setup. Due to a number of differences between the two plugin setups, be sure to start off with the files for the one you're targeting. The default is "Setup A", "Setup B (COOPANS)" must be specifically activated in the plugin settings file (TopSkySettings.txt, in the same folder with the plugin dll) by entering "Setup_COOPANS=1".

The definitions contain some items from the "Ground Radar plugin", but if that plugin is not in use, the items will only display "???" and can be safely removed.