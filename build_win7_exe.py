import os
import sys
import argparse
import subprocess

def get_target_python_info(py_path: str):
    """获取指定 Python 解释器的版本与有效性"""
    try:
        cmd = [py_path, "-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}'); print(sys.executable)"]
        output = subprocess.check_output(cmd, universal_newlines=True).strip().splitlines()
        version_str = output[0]
        exe_path = output[1]
        major, minor = map(int, version_str.split("."))
        return major, minor, exe_path
    except Exception as e:
        print(f"❌ 无法启动指定的 Python 解释器 [{py_path}]: {e}")
        sys.exit(1)

def build():
    parser = argparse.ArgumentParser(description="PC微信添加工具 - Windows 7 兼容包编译脚本")
    parser.add_argument(
        "-p", "--python",
        dest="target_python",
        default=sys.executable,
        help="指定用于打包的 Python 解释器绝对路径 (例如: C:\\Python38\\python.exe 或虚拟环境下的 python.exe)"
    )
    args = parser.parse_args()

    # 1. 探测并校验目标 Python 环境
    major, minor, target_python = get_target_python_info(args.target_python)
    print(f"🔍 当前打包选用 Python 环境: {target_python} (版本: {major}.{minor})")

    # 2. 检查 Win7 兼容性
    if (major, minor) > (3, 8):
        print(f"⚠️  警告: 检测到当前指定的 Python 版本为 {major}.{minor}！")
        print("    Python 3.9+ 官方已彻底放弃 Windows 7 支持。")
        print("    若要生成的 EXE 能在 Win7 正常启动，请务必使用【Python 3.8.10】！\n")
        confirm = input("是否仍要强行继续打包？(y/N): ").strip().lower()
        if confirm != 'y':
            sys.exit(1)

    # 3. 确保目标 Python 安装了 PyInstaller
    try:
        subprocess.check_call([target_python, "-c", "import PyInstaller"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        print(f"正在为 [{target_python}] 安装 PyInstaller...")
        subprocess.check_call([target_python, "-m", "pip", "install", "pyinstaller"])

    project_dir = os.path.dirname(os.path.abspath(__file__))
    main_script = os.path.join(project_dir, "main.py")
    icon_file = os.path.join(project_dir, "app_icon.ico")

    # 4. 构建打包命令
    cmd = [
        target_python, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--name=PC微信半自动添加工具_Win7通用版",
        "--uac-admin",
        "--win-private-assemblies",  # 携带私有 CRT 运行库，避免 Win7 报丢失 VC runtime
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

    print("\n🚀 开始编译单文件 EXE...")
    print("执行命令:", " ".join(cmd))
    subprocess.check_call(cmd)

    output_exe = os.path.join(project_dir, "dist", "PC微信半自动添加工具_Win7通用版.exe")
    print(f"\n🎉 打包完成！生成文件位于:\n{output_exe}")

if __name__ == "__main__":
    build()
