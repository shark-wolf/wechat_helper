import os
import sys
import subprocess

def build_single():
    try:
        import PyInstaller
    except ImportError:
        print("未检测到 PyInstaller，正在安装打包工具...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    project_dir = os.path.dirname(os.path.abspath(__file__))
    main_script = os.path.join(project_dir, "main.py")
    icon_file = os.path.join(project_dir, "app_icon.ico")

    # 构建一键纯单文件打包命令
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",                                   # 严格打成单个独立 EXE 文件
        "--windowed",                                  # 不弹出控制台黑框
        "--name=PC微信半自动添加工具",
        "--uac-admin",                                 # 强制请求管理员权限运行
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

    # 图标打包（若存在）
    if os.path.exists(icon_file):
        cmd.append(f"--icon={icon_file}")
        cmd.append(f"--add-data={icon_file};.")

    # 载入主入口脚本
    cmd.append(main_script)

    print("🚀 开始编译打包所有依赖环境与脚本到单个 EXE 文件，请稍候...")
    print(" ".join(cmd))
    subprocess.check_call(cmd)
    print("\n🎉 打包完成！生成的可执行文件位于：")
    print(os.path.join(project_dir, "dist", "PC微信半自动添加工具.exe"))

if __name__ == "__main__":
    build_single()
