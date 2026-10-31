
import argparse

from interfaces.cli.auth import login, logout, status


def main() -> None:
    parser = argparse.ArgumentParser(
        description="LibSocial CLI"
    )

    parser.add_argument(
        "command",
        choices=["login", "status", "logout"],
        help="Команда для выполнения",
    )

    args = parser.parse_args()

    commands = {
        "login": login,
        "status": status,
        "logout": logout,
    }

    commands[args.command]()


if __name__ == "__main__":
    main()
