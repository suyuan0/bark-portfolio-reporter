from dataclasses import dataclass
from pathlib import Path
import re
import subprocess


BEGIN_MARKER = "# bark-portfolio-reporter BEGIN"
END_MARKER = "# bark-portfolio-reporter END"
DEFAULT_WEEKDAYS = "1-5"


@dataclass
class CronConfig:
    enabled: bool
    minute: int
    hour: int
    weekdays: str
    project_dir: str
    python_path: str
    script_path: str
    log_path: str


def build_cron_command(config: CronConfig) -> str:
    return (
        f"cd {config.project_dir} && "
        f"{config.python_path} {config.script_path} >> {config.log_path} 2>&1"
    )


def build_cron_line(config: CronConfig) -> str:
    line = (
        f"{config.minute} {config.hour} * * {config.weekdays} "
        f"{build_cron_command(config)}"
    )

    if not config.enabled:
        return f"# {line}"

    return line


def build_cron_block(config: CronConfig) -> str:
    return "\n".join([BEGIN_MARKER, build_cron_line(config), END_MARKER])


def is_legacy_project_cron_line(line: str, config: CronConfig) -> bool:
    stripped_line = line.strip()

    if stripped_line in [BEGIN_MARKER, END_MARKER]:
        return False

    uncommented_line = stripped_line[1:].strip() if stripped_line.startswith("#") else stripped_line

    return (
        f"cd {config.project_dir} &&" in uncommented_line
        and f" {config.script_path} >>" in uncommented_line
    )


def remove_legacy_project_cron_lines(crontab_text: str, config: CronConfig) -> str:
    lines = crontab_text.splitlines()
    kept_lines = [
        line
        for line in lines
        if not is_legacy_project_cron_line(line, config)
    ]

    return "\n".join(kept_lines)


def replace_project_cron_block(crontab_text: str, config: CronConfig) -> str:
    crontab_text = remove_legacy_project_cron_lines(crontab_text, config).strip("\n")
    block = build_cron_block(config)
    pattern = re.compile(
        rf"{re.escape(BEGIN_MARKER)}.*?{re.escape(END_MARKER)}",
        flags=re.DOTALL,
    )

    if pattern.search(crontab_text):
        return pattern.sub(block, crontab_text).strip("\n") + "\n"

    if not crontab_text:
        return block + "\n"

    return crontab_text + "\n" + block + "\n"


def parse_project_cron_block(crontab_text: str) -> CronConfig | None:
    pattern = re.compile(
        rf"{re.escape(BEGIN_MARKER)}\n(?P<line>.*?)\n{re.escape(END_MARKER)}",
        flags=re.DOTALL,
    )
    match = pattern.search(crontab_text)

    if not match:
        return None

    raw_line = match.group("line").strip()
    enabled = not raw_line.startswith("#")
    line = raw_line[1:].strip() if not enabled else raw_line

    parts = line.split(maxsplit=5)
    if len(parts) != 6:
        return None

    minute, hour, _, _, weekdays, command = parts
    command_match = re.match(
        r"cd (?P<project_dir>.+?) && (?P<python_path>\S+) "
        r"(?P<script_path>\S+) >> (?P<log_path>\S+) 2>&1$",
        command,
    )

    if not command_match:
        return None

    try:
        minute_value = int(minute)
        hour_value = int(hour)
    except ValueError:
        return None

    return CronConfig(
        enabled=enabled,
        minute=minute_value,
        hour=hour_value,
        weekdays=weekdays,
        project_dir=command_match.group("project_dir"),
        python_path=command_match.group("python_path"),
        script_path=command_match.group("script_path"),
        log_path=command_match.group("log_path"),
    )


def default_cron_config(project_root: Path, python_path: str) -> CronConfig:
    return CronConfig(
        enabled=False,
        minute=30,
        hour=15,
        weekdays=DEFAULT_WEEKDAYS,
        project_dir=str(project_root),
        python_path=python_path,
        script_path="src/main.py",
        log_path="logs/app.log",
    )


def read_user_crontab() -> str:
    result = subprocess.run(
        ["crontab", "-l"],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode == 0:
        return result.stdout

    if "no crontab for" in result.stderr.lower():
        return ""

    raise RuntimeError(result.stderr.strip() or "读取 crontab 失败")


def write_user_crontab(crontab_text: str):
    result = subprocess.run(
        ["crontab", "-"],
        input=crontab_text,
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "写入 crontab 失败")
