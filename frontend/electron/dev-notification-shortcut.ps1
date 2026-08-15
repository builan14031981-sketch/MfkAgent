param(
  [Parameter(Mandatory = $true)]
  [string]$TargetExe
)

# ============================================================
# MfkAgent Dev notification identity bootstrap script
#
# Windows 10/11 requires the toast AppUserModelId to match a
# Start-Menu shortcut carrying the System.AppUserModel.ID
# property, otherwise notifications are silently dropped
# (beep only, no toast). Packaged builds get this shortcut from
# the NSIS installer; dev mode (npx electron .) uses this script.
#
# Usage: powershell -File dev-notification-shortcut.ps1 -TargetExe <electron.exe>
# ============================================================

$ErrorActionPreference = "Stop"
$AUMID = "com.mfkagent.app"
$shortcutName = "MfkAgent Dev.lnk"
$startMenuDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
$shortcutPath = Join-Path $startMenuDir $shortcutName

try {
  # NOTE: keep the C# here-string ASCII-only (English comments).
  # Non-ASCII comments here get mis-decoded by Add-Type on some
  # codepages and break the C# line structure.
  $typeDef = @"
using System;
using System.Runtime.InteropServices;
using System.Runtime.InteropServices.ComTypes;

public static class ShortcutFactory
{
    [ComImport]
    [Guid("00021401-0000-0000-C000-000000000046")]
    public class ShellLink { }

    [ComImport]
    [InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    [Guid("000214F9-0000-0000-C000-000000000046")]
    public interface IShellLinkW
    {
        void GetPath([Out, MarshalAs(UnmanagedType.LPWStr)] System.Text.StringBuilder pszFile, int cch, IntPtr pfd, uint fFlags);
        void GetIDList(out IntPtr ppidl);
        void SetIDList(IntPtr pidl);
        void GetDescription([Out, MarshalAs(UnmanagedType.LPWStr)] System.Text.StringBuilder pszName, int cch);
        void SetDescription([MarshalAs(UnmanagedType.LPWStr)] string pszName);
        void GetWorkingDirectory([Out, MarshalAs(UnmanagedType.LPWStr)] System.Text.StringBuilder pszDir, int cch);
        void SetWorkingDirectory([MarshalAs(UnmanagedType.LPWStr)] string pszDir);
        void GetArguments([Out, MarshalAs(UnmanagedType.LPWStr)] System.Text.StringBuilder pszArgs, int cch);
        void SetArguments([MarshalAs(UnmanagedType.LPWStr)] string pszArgs);
        void GetHotkey(out ushort pwHotkey);
        void SetHotkey(ushort wHotkey);
        void GetShowCmd(out int piShowCmd);
        void SetShowCmd(int iShowCmd);
        void GetIconLocation([Out, MarshalAs(UnmanagedType.LPWStr)] System.Text.StringBuilder pszIconPath, int cch, out int piIcon);
        void SetIconLocation([MarshalAs(UnmanagedType.LPWStr)] string pszIconPath, int iIcon);
        void SetRelativePath([MarshalAs(UnmanagedType.LPWStr)] string pszPathRel, uint dwReserved);
        void Resolve(IntPtr hwnd, uint fFlags);
        void SetPath([MarshalAs(UnmanagedType.LPWStr)] string pszFile);
    }

    [ComImport]
    [Guid("0000010B-0000-0000-C000-000000000046")]
    [InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    public interface IPersistFile
    {
        // Must declare IPersist.GetClassID first, otherwise the
        // vtable shifts and Save actually calls Load (S_OK but no file).
        void GetClassID(out Guid pClassID);
        [PreserveSig] int IsDirty();
        [PreserveSig] int Load([MarshalAs(UnmanagedType.LPWStr)] string pszFileName, uint dwMode);
        [PreserveSig] int Save([MarshalAs(UnmanagedType.LPWStr)] string pszFileName, [MarshalAs(UnmanagedType.Bool)] bool fRemember);
        [PreserveSig] int SaveCompleted([MarshalAs(UnmanagedType.LPWStr)] string pszFileName);
        [PreserveSig] int GetCurFile([Out, MarshalAs(UnmanagedType.LPWStr)] System.Text.StringBuilder pszFileName);
    }

    [StructLayout(LayoutKind.Sequential, Pack = 4)]
    public struct PROPVARIANT
    {
        public ushort vt;
        public ushort wReserved1;
        public ushort wReserved2;
        public ushort wReserved3;
        public IntPtr pValue;
    }

    [StructLayout(LayoutKind.Sequential, Pack = 4)]
    public struct PROPERTYKEY
    {
        public Guid fmtid;
        public uint pid;
    }

    [ComImport]
    [Guid("886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99")]
    [InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    public interface IPropertyStore
    {
        int GetCount(out uint cProps);
        int GetAt(uint iProp, out IntPtr pkey);
        int GetValue(ref PROPERTYKEY key, out PROPVARIANT pv);
        int SetValue(ref PROPERTYKEY key, ref PROPVARIANT pv);
        int Commit();
    }

    public static string Create(string shortcutPath, string target, string aumid)
    {
        // 1. Create the base IShellLink object and set its target/icon.
        ShellLink link = new ShellLink();
        IShellLinkW sl = (IShellLinkW)link;
        sl.SetPath(target);
        sl.SetIconLocation(target, 0);

        // 2. Set PKEY_AppUserModel_ID through the IShellLink property store
        //    BEFORE calling IPersistFile::Save. MSDN documents this order for
        //    shortcuts: setting the property on the in-memory object, then
        //    Save persists it into the .lnk. (Setting it on the file's own
        //    property store is read-only for .lnk and never sticks.)
        Guid iid = new Guid("886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99"); // IID_IPropertyStore
        IntPtr slPtr = Marshal.GetComInterfaceForObject(sl, typeof(IShellLinkW));
        IntPtr storePtr;
        int hr = Marshal.QueryInterface(slPtr, ref iid, out storePtr);
        Marshal.Release(slPtr);
        if (hr != 0) return "FAIL:QueryInterface=" + hr;

        IPropertyStore store = (IPropertyStore)Marshal.GetObjectForIUnknown(storePtr);

        // PKEY_AppUserModel_ID = {9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3}, pid=5
        PROPERTYKEY key = new PROPERTYKEY();
        key.fmtid = new Guid("9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3");
        key.pid = 5;
        PROPVARIANT pv = new PROPVARIANT();
        pv.vt = 31; // VT_LPWSTR
        pv.pValue = Marshal.StringToCoTaskMemUni(aumid);
        int hrSet = store.SetValue(ref key, ref pv);
        Marshal.FreeCoTaskMem(pv.pValue);
        int hrCom = store.Commit();
        Marshal.Release(storePtr);
        if (hrSet != 0) return "FAIL:SetValue=" + hrSet;
        if (hrCom != 0) return "FAIL:Commit=" + hrCom;

        // 3. Save the shortcut to disk (persists the AUMID set above).
        IPersistFile pf = (IPersistFile)link;
        int hrSave = pf.Save(shortcutPath, true);
        if (hrSave != 0) return "FAIL:Save=" + hrSave;
        return "OK";
    }
}
"@

  Add-Type -TypeDefinition $typeDef -Language CSharp

  if (-not (Test-Path $startMenuDir)) {
    New-Item -ItemType Directory -Path $startMenuDir -Force | Out-Null
  }

  $result = [ShortcutFactory]::Create($shortcutPath, $TargetExe, $AUMID)

  if (Test-Path $shortcutPath) {
    Write-Output "SHORTCUT_OK:$shortcutPath CREATE=$result"
  } else {
    Write-Output "SHORTCUT_FAIL:file not created CREATE=$result"
    exit 1
  }
} catch {
  Write-Output "SHORTCUT_FAIL:$($_.Exception.Message)"
  exit 1
}
