"""
================================================================================
                    PC微信半自动添加工具 - Windows 7 兼容打包脚本
================================================================================

【功能说明】
    用于将当前项目打包为单个独立 EXE 可执行文件，针对 Windows 7 环境做专门兼容处理：
    1. 自动检测指定的 Python 版本（Win7 必须使用 Python <= 3.8，推荐 3.8.10）；
    2. 支持在任何外部 Python 环境下，通过参数指向已安装的 Python 3.8.10 解释器进行编译；
    3. 适配 PyInstaller 6.0+ 参数规范，移除了已被弃用的 --win-private-assemblies 标志；
    4. 显式排除 Win10/11 专有的 api-ms-win-core-* 虚拟转发库，彻底解决 Win7 报 DLL 丢失问题。

【命令行参数说明】
    -p, --python [路径]
        指定实际用于打包的目标 Python 解释器绝对路径。
        默认值：当前正在运行本脚本的 Python 解释器 (sys.executable)。

【常见用法示例】
    1. 使用当前默认 Python 环境打包:
       python build_win7_exe.py

    2. 指向全局安装的 Python 3.8.10 解释器路径:
       python build_win7_exe.py -p D:\\apps\\python-3.8.10\\python.exe
       python build_win7_exe.py --python "C:\\Program Files\\Python38\\python.exe"

    3. 指向 Python 3.8 虚拟环境解释器路径:
       python build_win7_exe.py -p D:\\envs\\py38_win7\\Scripts\\python.exe

    4. 查看帮助文档:
       python build_win7_exe.py --help
================================================================================
"""

import os
import sys
import argparse
import subprocess

USAGE_EXAMPLES = """
常见使用示例:
  1. 使用当前默认 Python 环境打包:
     python build_win7_exe.py

  2. 指定系统的 Python 3.8.10 解释器进行打包:
     python build_win7_exe.py -p D:\\apps\\python-3.8.10\\python.exe
     python build_win7_exe.py --python "C:\\Program Files\\Python38\\python.exe"

  3. 指定虚拟环境中的 Python 3.8 解释器:
     python build_win7_exe.py -p D:\\envs\\py38_win7\\Scripts\\python.exe
"""

PIP_MIRROR = "https://pypi.tuna.tsinghua.edu.cn/simple"
TRUSTED_HOST = "pypi.tuna.tsinghua.edu.cn"

def get_target_python_info(py_path: str):
    """获取指定 Python 解释器的版本与物理执行路径"""
    try:
        cmd = [
            py_path,
            "-c",
            "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}'); print(sys.executable)"
        ]
        output = subprocess.check_output(cmd, universal_newlines=True).strip().splitlines()
        version_str = output[0]
        exe_path = output[1]
        major, minor = map(int, version_str.split("."))
        return major, minor, exe_path
    except Exception as e:
        print(f"❌ 无法启动指定的 Python 解释器 [{py_path}]: {e}")
        sys.exit(1)

def ensure_dependencies(target_python: str):
    """检查并确保目标环境具备 PyInstaller 及项目运行所需的关键第三方包"""
    # 1. 检查 PyInstaller
    try:
        subprocess.check_call([target_python, "-c", "import PyInstaller"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        print(f"正在为 [{target_python}] 自动安装 PyInstaller（使用清华镜像源）...")
        try:
            subprocess.check_call([
                target_python, "-m", "pip", "install", "pyinstaller",
                "-i", PIP_MIRROR,
                "--trusted-host", TRUSTED_HOST
            ])
        except subprocess.CalledProcessError:
            print("\n" + "=" * 70)
            print("❌ 自动安装 PyInstaller 失败！")
            print("请手动执行以下命令修复环境并安装依赖：")
            print(f'"{target_python}" -m pip install -i {PIP_MIRROR} pyinstaller pandas==1.5.3 openpyxl pywinauto pywin32 pyperclip')
            print("=" * 70 + "\n")
            sys.exit(1)

    # 2. 检查 pywin32 / win32gui
    try:
        subprocess.check_call([target_python, "-c", "import win32gui"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        print(f"检测到缺少 pywin32，正在为 [{target_python}] 自动安装...")
        try:
            subprocess.check_call([
                target_python, "-m", "pip", "install", "pywin32",
                "-i", PIP_MIRROR,
                "--trusted-host", TRUSTED_HOST
            ])
        except Exception:
            pass

def build():
    parser = argparse.ArgumentParser(
        description="PC微信半自动添加工具 - Windows 7 兼容单文件 EXE 打包脚本",
        epilog=USAGE_EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "-p", "--python",
        dest="target_python",
        default=sys.executable,
        help="指定用于执行打包的 Python 解释器绝对路径 (例如: D:\\apps\\python-3.8.10\\python.exe)。默认使用当前环境。"
    )
    args = parser.parse_args()

    # 1. 探测并校验目标 Python 环境
    major, minor, target_python = get_target_python_info(args.target_python)
    print(f"🔍 当前打包选用的 Python 解释器: {target_python} (版本: {major}.{minor})")

    # 2. 检查 Win7 兼容性版本硬限制
    if (major, minor) > (3, 8):
        print(f"\n⚠️  警告: 检测到目标 Python 版本为 {major}.{minor}！")
        print("    Python 3.9 及以上版本官方已彻底移除 Windows 7 支持。")
        print("    如果要在 Win7 稳定运行，必须使用【Python 3.8.10】进行打包！\n")
        confirm = input("是否仍要强行继续打包？(y/N): ").strip().lower()
        if confirm != 'y':
            sys.exit(1)

    # 3. 依赖就绪检查
    ensure_dependencies(target_python)

    project_dir = os.path.dirname(os.path.abspath(__file__))
    main_script = os.path.join(project_dir, "main.py")
    icon_file = os.path.join(project_dir, "app_icon.ico")

    # 4. 关键：排除 Win10/11 虚拟重定向垫片库，让 Win7 强制使用系统原生的 kernel32.dll
    exclude_dlls = [
        "api-ms-win-core-kernel32-legacy-l1-1-1.dll",
        "api-ms-win-core-kernel32-legacy-l1-1-0.dll",
        "api-ms-win-core-kernel32-private-l1-1-1.dll",
        "api-ms-win-core-kernel32-private-l1-1-0.dll",
        "api-ms-win-core-path-l1-1-0.dll"
    ]

    # 5. 组装 PyInstaller 命令参数
    cmd = [
        target_python, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--name=PC微信半自动添加工具_Win7通用版",
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

    # 注入排除参数
    for dll in exclude_dlls:
        cmd.extend(["--exclude-module", dll])
        cmd.extend(["--exclude-module", dll.replace(".dll", "")])

    if os.path.exists(icon_file):
        cmd.append(f"--icon={icon_file}")
        cmd.append(f"--add-data={icon_file};.")

    cmd.append(main_script)

    print("\n🚀 开始编译单文件 EXE (已排除 Win10 专有 API-MS DLL)...")
    print("执行命令:", " ".join(cmd))
    subprocess.check_call(cmd)

    output_exe = os.path.join(project_dir, "dist", "PC微信半自动添加工具_Win7通用版.exe")
    print(f"\n🎉 打包完成！生成文件位于:\n{output_exe}")

if __name__ == "__main__":
    build()
