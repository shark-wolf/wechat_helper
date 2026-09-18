import os
import sys
import subprocess

def build_single():
    try:
        import PyInstaller
    except ImportError:
        print("未检测到 PyInstaller，正在安装打包依赖...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    project_dir = os.path.dirname(os.path.abspath(__file__))
    main_script = os.path.join(project_dir, "main.py")
    icon_file = os.path.join(project_dir, "app_icon.ico")

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--name=PC微信半自动添加工具",
        "--uac-admin",
        "--hidden-import=pywinauto",
        "--hidden-import=win32gui",
        "--hidden-import=win32con",
        "--hidden-import=win32api",
        "--hidden-import=win32process",
        "--hidden-import=win32ui",
        "--hidden-import=openpyxl",
        "--hidden-import=pandas",
        "--hidden-import=pyperclip",
    ]

    if os.path.exists(icon_file):
        cmd.append(f"--icon={icon_file}")
        cmd.append(f"--add-data={icon_file};.")

    cmd.append(main_script)

    print("🚀 开始编译打包所有依赖环境至单个独立 EXE，请稍候...")
    print(" ".join(cmd))
    subprocess.check_call(cmd)
    print("\n🎉 打包完成！独立 EXE 位于：")
    print(os.path.join(project_dir, "dist", "PC微信半自动添加工具.exe"))

if __name__ == "__main__":
    build_single()
