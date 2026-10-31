import argparse
from importlib.metadata import PackageNotFoundError, version

from interfaces.cli.auth import login, logout, status
from interfaces.cli.download import configure_parser, execute


def main() -> None:
    parser = argparse.ArgumentParser(description='RanobeLib CLI')
    try:
        package_version = version("ranobe-downloader")
    except PackageNotFoundError:
        package_version = "0.1.0a1"
    parser.add_argument("--version", action="version", version=f"%(prog)s {package_version}")
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('login', 'status', 'logout'):
        sub.add_parser(name)
    download = sub.add_parser('download', help='Download a complete EPUB')
    configure_parser(download)
    args = parser.parse_args()
    if args.command == 'download':
        execute(args)
    else:
        {'login': login, 'status': status, 'logout': logout}[args.command]()


if __name__ == '__main__':
    main()
