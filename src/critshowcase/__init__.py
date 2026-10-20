"""CRITShowCase（B50 影片）的出片工具。"""
from importlib.metadata import PackageNotFoundError, version


def package_version(package: str) -> str:
    """回報問題時要附的版本；套件沒裝時顯示（未安裝）。"""
    try:
        return version(package)
    except PackageNotFoundError:
        return "（未安裝）"
