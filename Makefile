APP_NAME := workforce
MAIN_SCRIPT := run.py

DIST_DIR := dist
BUILD_DIR := build
PKG_DIR := package

ICON_WIN := docs/images/icon.ico
ICON_MAC := docs/images/icon.icns
ICON_LINUX := docs/images/icon.xbm

.PHONY: all clean linux windows mac

all: linux windows mac

# 1. Linux: Build binary + .deb package
linux: pyinstaller-linux deb-package

pyinstaller-linux:
	pyinstaller --onefile --windowed --icon=$(ICON_LINUX) --name=$(APP_NAME) \
		--distpath $(DIST_DIR)/linux --workpath $(BUILD_DIR)/linux \
		$(MAIN_SCRIPT)

deb-package:
	# Create directory structure for Debian package
	mkdir -p $(PKG_DIR)/$(APP_NAME)/usr/local/bin
	cp $(DIST_DIR)/linux/$(APP_NAME) $(PKG_DIR)/$(APP_NAME)/usr/local/bin/

	# Create DEBIAN control file
	mkdir -p $(PKG_DIR)/$(APP_NAME)/DEBIAN
	echo "Package: $(APP_NAME)" > $(PKG_DIR)/$(APP_NAME)/DEBIAN/control
	echo "Version: 1.0" >> $(PKG_DIR)/$(APP_NAME)/DEBIAN/control
	echo "Section: utils" >> $(PKG_DIR)/$(APP_NAME)/DEBIAN/control
	echo "Priority: optional" >> $(PKG_DIR)/$(APP_NAME)/DEBIAN/control
	echo "Architecture: amd64" >> $(PKG_DIR)/$(APP_NAME)/DEBIAN/control
	echo "Maintainer: Your Name <you@example.com>" >> $(PKG_DIR)/$(APP_NAME)/DEBIAN/control
	echo "Description: My awesome app" >> $(PKG_DIR)/$(APP_NAME)/DEBIAN/control

	# Build deb package
	dpkg-deb --build $(PKG_DIR)/$(APP_NAME) $(DIST_DIR)/$(APP_NAME)_linux_amd64.deb

# 2. Windows: Build binary + Inno Setup installer
windows: pyinstaller-windows inno-setup

pyinstaller-windows:
	pyinstaller --onefile --windowed --icon=$(ICON_WIN) \
		--distpath $(DIST_DIR)/windows --workpath $(BUILD_DIR)/windows \
		$(MAIN_SCRIPT)

inno-setup:
	# Run Inno Setup compiler from WSL using Windows path
	/mnt/c/Users/tpor598/AppData/Local/Programs/Inno\ Setup\ 6/ISCC.exe installer.iss

# 3. macOS: Build binary + pkg installer
mac: pyinstaller-mac pkgbuild

pyinstaller-mac:
	pyinstaller --onefile --windowed --icon=$(ICON_MAC) \
		--distpath $(DIST_DIR)/mac --workpath $(BUILD_DIR)/mac \
		$(MAIN_SCRIPT)

pkgbuild:
	# Create pkg installer - adjust --install-location as needed
	pkgbuild --root $(DIST_DIR)/mac --identifier com.yourcompany.$(APP_NAME) \
		--version 1.0 --install-location /Applications/$(APP_NAME).app \
		$(DIST_DIR)/$(APP_NAME).pkg

clean:
	rm -rf $(DIST_DIR) $(BUILD_DIR) $(PKG_DIR) *.spec

