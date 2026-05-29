; NSIS installer script template for DMS_Client (Modern UI)
; Supports: create Start Menu entry, desktop shortcut, optional run-at-startup, and uninstall
; Usage: makensis /DAPP_EXE="DMS_Client_20260528_143052.exe" /DOUTFILE="releases\DMS_Client_Installer.exe" installer\dms_installer.nsi

!include MUI2.nsh

; Define defaults (can be overridden via command line)
!ifndef APP_NAME
  !define APP_NAME "DMS Client"
!endif
!ifndef APP_EXE
  !define APP_EXE "DMS_Client.exe"
!endif
!ifndef APP_EXE_PATH
  !define APP_EXE_PATH "releases\DMS_Client.exe"
!endif
!ifndef APP_INSTALL_EXE
  !define APP_INSTALL_EXE "DMS_Client.exe"
!endif
!ifndef APP_LICENSE_PATH
  !define APP_LICENSE_PATH ""
!endif
!ifndef OUTFILE
  !define OUTFILE "releases\DMS_Client_Installer.exe"
!endif
!ifndef INSTALL_DIR
  !define INSTALL_DIR "$PROGRAMFILES64\DMS_Client"
!endif

SetCompressor /SOLID lzma
OutFile ${OUTFILE}
InstallDir ${INSTALL_DIR}

; Pages
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_COMPONENTS
Page directory
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

Section "Main Files" SEC_MAIN
    SetOutPath "$INSTDIR"
  File /oname=$INSTDIR\${APP_INSTALL_EXE} ${APP_EXE_PATH}
!if "${APP_LICENSE_PATH}" != ""
  File "${APP_LICENSE_PATH}"
!endif
    CreateDirectory "$APPDATA\DMS"
    CreateDirectory "$APPDATA\DMS\uploads"
    WriteUninstaller "$INSTDIR\Uninstall.exe"
SectionEnd

Section "Create Desktop Icon" SEC_DESKTOP
  CreateShortcut "$DESKTOP\${APP_NAME}.lnk" "$INSTDIR\${APP_INSTALL_EXE}"
SectionEnd

Section "Run at Startup" SEC_STARTUP
    ; Write Run key for current user to enable start-on-login
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "DMS_Client" '"$INSTDIR\${APP_INSTALL_EXE}"'
SectionEnd

Section "Uninstall"
    Delete "$DESKTOP\${APP_NAME}.lnk"
    Delete "$SMPROGRAMS\${APP_NAME}.lnk"
    Delete "$INSTDIR\${APP_INSTALL_EXE}"
    Delete "$INSTDIR\Uninstall.exe"
    ; Remove run-at-startup registry key if present
    DeleteRegValue HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "DMS_Client"
    RMDir "$APPDATA\DMS\uploads"
    RMDir "$APPDATA\DMS"
    RMDir "$INSTDIR"
SectionEnd

; MUI language
!insertmacro MUI_LANGUAGE "English"
